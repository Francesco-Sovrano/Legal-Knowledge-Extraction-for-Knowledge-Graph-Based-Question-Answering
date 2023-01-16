import os
import pickle
import numpy as np # for fast array ops
import misc.tfidf_lib as tfidf_lib
from models.model_manager import ModelManager
from sklearn.metrics.pairwise import cosine_similarity
from nltk.stem.snowball import SnowballStemmer # <http://www.nltk.org/howto/stem.html>

from misc.doc_reader import load_or_create_cache, create_cache, load_cache

class SentenceClassifier(ModelManager):
	stemmer = SnowballStemmer("english")

	def __init__(self, model_options):
		super().__init__(model_options)
		self.disable_spacy_component = ["tagger", "ner", "textcat", "neuralcoref"]
		# Read options from input
		self.log = model_options.get('log', False)
		self.use_tf_model = model_options.get('tf_model', None) is not None
		self.with_topic_scaling = model_options.get('with_topic_scaling', False)
		self.use_combined_wordvec = self.with_topic_scaling or not self.use_tf_model
		self.with_document_log_length_scaling = model_options.get('with_document_log_length_scaling', False)
		self.with_centered_similarity = model_options.get('with_centered_similarity', False)
		# TF-IDF
		self.default_tfidf_importance = model_options.get('default_tfidf_importance', 1/2) # number in [0,1]
		self.default_tfidf_importance = np.clip(self.default_tfidf_importance, 0,1)
		self.with_stemmed_tfidf = model_options.get('with_stemmed_tfidf', False)
		self.very_big_corpus = model_options.get('very_big_corpus', False)
		self.query_cache = {}
		self.default_similarity_threshold = self.model_options.get('default_similarity_threshold', 0)
		
		if self.log:
			print('Initialising SentenceClassifier:')
			print('  with_stemmed_tfidf',self.with_stemmed_tfidf)
			print('  with_topic_scaling',self.with_topic_scaling)
			print('  with_document_log_length_scaling',self.with_document_log_length_scaling)
			print('  default_tfidf_importance',self.default_tfidf_importance)
			print('  use_combined_wordvec',self.use_combined_wordvec)

	def set_documents(self, id_doc_list, context_list=None):
		self.ids, self.documents = zip(*id_doc_list)
		self.contexts = context_list if context_list else list(self.documents)
		self.contextualised_documents = list(zip(self.documents,self.contexts))
		if self.use_tf_model:
			self.contextualised_documents_embeddings = self.run_tf_embedding(doc_list=self.contextualised_documents, as_question=False)
		self.target_size = len(id_doc_list)
		# TF-IDF
		self.tfidf_prepared = False
		self.spacy_prepared = False
		return self

	def get_stemmed_token_list(self, token_list):
		return list(map(self.stemmer.stem, token_list))

	def prepare_tfidf(self):
		# Get lemmatized documents
		lemmatized_document_iter = map(self.lemmatize_spacy_document, self.spacy_documents)
		if self.with_stemmed_tfidf:
			stemmed_documents = [
				self.get_stemmed_token_list(token_list)
				for token_list in lemmatized_document_iter
			]
			if self.log:
				print('stemmed_documents', stemmed_documents)
			words_vector = stemmed_documents 
		else:
			words_vector = list(lemmatized_document_iter)
		# Build tf-idf model and similarities
		dictionary, tfidf_model, tfidf_corpus_similarities = tfidf_lib.build_tfidf(words_vector=words_vector, very_big_corpus=self.very_big_corpus)
		if self.log:
			print("Number of words in dictionary:",len(dictionary))
		self.dictionary, self.tfidf_model, self.tfidf_corpus_similarities = dictionary, tfidf_model, tfidf_corpus_similarities
		self.tfidf_prepared = True

	def prepare_spacy(self):
		if not self.spacy_prepared:
			self.spacy_documents = self.nlp(self.contexts)
			self.spacy_prepared = True
	
	def lemmatize_spacy_document(self, doc):
		return [
			token.lemma_.casefold().strip()
			for token in doc
			if not (token.is_stop or token.is_punct) and token.lemma_.lower() != '-pron-'
		]

	def get_weighted_similarity(self, similarity_dict, query_length, tfidf_importance):
		semantic_similarity = similarity_dict.get('docvec' if self.use_tf_model else 'combined_wordvec', 0)
		syntactic_similarity = similarity_dict.get('tfidf', 0)
		# Build combined similarity
		if self.log:
			print('tfidf_importance', tfidf_importance)
		weighted_similarity = tfidf_importance*syntactic_similarity+(1-tfidf_importance)*semantic_similarity
				
		if self.with_topic_scaling:
			# Get the topic weight
			corpus_similarity = similarity_dict['corpus']
			topic_weight = np.power(corpus_similarity,2)
			# Compute the weighted similarity for every sub-corpus
			# syntactic_similarity is high for a document when the query words and the document words are similar, but syntactic_similarity may be lower when we use words in the synsets
			# in order to address the aforementioned synset-words problem we sum the syntactic_similarity with the corpus_similarity before scaling it by the semantic_weight
			# we scale by the semantic_weight in order to give significantly more similarity to the documents semantically more closer to the query 
			weighted_similarity *= topic_weight
			
		if self.with_document_log_length_scaling:
			# the bigger the sentence, the (smoothly) lower the weighted_similarity
			# thus we scale the weighted_similarity by the log of the query length
			weighted_similarity *= np.array(query_length)/np.max(query_length) # sum 1 to avoid similarity zeroing
			
		return weighted_similarity

	def classify(self, query_list, similarity_type, similarity_threshold=None, as_question=False, tfidf_importance=None):
		return self.get_index_of_most_similar_documents(
			self.get_query_similarity(query_list, as_question=as_question, tfidf_importance=tfidf_importance), 
			similarity_threshold=similarity_threshold,
			similarity_type=similarity_type,
		)

	def get_query_similarity(self, query_list, as_question=False, tfidf_importance=None):
		return self.get_formatted_query_similarity(
			query_list, # original query
			self.nlp(query_list), # Get the filtered query (Document object built using lemmas)
			as_question=as_question,
			tfidf_importance=tfidf_importance,
		)

	def get_formatted_query_similarity(self, text_list, formatted_query_list, as_question=False, tfidf_importance=None):
		if tfidf_importance is None:
			tfidf_importance = self.default_tfidf_importance
		# Prepare spacy docs if they are not ready yet
		with_syntactic_similarity = tfidf_importance > 0
		with_semantic_similarity = tfidf_importance < 1
		if with_syntactic_similarity:
			self.prepare_spacy()
			self.prepare_tfidf()
		elif self.use_combined_wordvec:
			self.prepare_spacy()
		#################################################################################
		# Build similarity dict
		similarity_dict = {}
		if with_syntactic_similarity:
			# Get the lemmatized query
			formatted_query_list = tuple(map(self.lemmatize_spacy_document, formatted_query_list))
			if self.log:
				print('lemmatized_query', formatted_query_list)
			# Get the stemmed query for tf-idf
			if self.with_stemmed_tfidf:
				formatted_query_list = tuple(map(self.get_stemmed_token_list, formatted_query_list))
				if self.log:
					print('stemmed_query', formatted_query_list)
			# Get tf-idf and docvec similarities
			similarity_dict['tfidf'] = np.array([
				tfidf_lib.get_query_tfidf_similarity(
					formatted_query, 
					self.dictionary, 
					self.tfidf_model, 
					self.tfidf_corpus_similarities
				)
				for formatted_query in formatted_query_list
			])
		if with_semantic_similarity:
			if self.use_tf_model:
				# Get docvec similarity
				similarity_dict['docvec'] = np.inner(
					self.run_tf_embedding(doc_list=text_list, as_question=as_question),
					self.contextualised_documents_embeddings
				)
			if self.use_combined_wordvec:
				get_avg_wordvec_similarity = lambda x: np.mean([q.vector for q in x])
				# Get averaged wordvec similarity
				similarity_dict['combined_wordvec'] = cosine_similarity(
					map(get_avg_wordvec_similarity, formatted_query_list),
					map(get_avg_wordvec_similarity, self.spacy_documents)
				)
			if self.with_topic_scaling:
				# Get the corpus similarity for every sub-corpus, by averaging the docvec similarities of every sub-corpus
				similarity_dict['corpus'] = np.mean(similarity_dict['combined_wordvec'],-1)
				similarity_dict['corpus'] = np.expand_dims(similarity_dict['corpus'], -1) # expand_dims because we have sub-corpus
		# Get the weighted similarity
		similarity_dict['weighted'] = self.get_weighted_similarity(similarity_dict=similarity_dict, query_length=np.array(map(len,formatted_query_list)), tfidf_importance=tfidf_importance)
		# Sum the weighted similarity across sub-corpus
		# similarity_dict['weighted'] = np.sum(similarity_dict['weighted'], 0)
		# Center the weighted_similarity vector
		if self.with_centered_similarity:
			# Center the weighted_similarity vector: Remove the average weighted_similarity
			similarity_dict['weighted'] -= np.mean(similarity_dict['weighted'])
			# Remove negative components, they are useless for the task
			similarity_dict['weighted'] = np.maximum(similarity_dict['weighted'], 0)
		return similarity_dict
	
	def get_index_of_most_similar_documents(self, similarity_dict, similarity_type, similarity_threshold=None):
		if similarity_threshold is None:
			similarity_threshold = self.default_similarity_threshold
		def get_similarity_dict_generator(i, similarity_ranking):
			# print('#'*100)
			similarity = similarity_dict[similarity_type][i]
			syntactic_similarity = similarity_dict['tfidf'][i] if 'tfidf' in similarity_dict else None
			semantic_similarity = similarity_dict['docvec'][i] if 'docvec' in similarity_dict else None
			for best in similarity_ranking:
				if similarity_threshold is not None and similarity[best] < similarity_threshold:
					return
				sim_dict = {
					'id':self.ids[best], 
					'doc':self.documents[best], 
					'index':int(best), 
					'similarity':float(similarity[best]),
					'syntactic_similarity':float(syntactic_similarity[best]) if syntactic_similarity is not None else 0,
					'semantic_similarity':float(semantic_similarity[best]) if semantic_similarity is not None else 0,
				}
				# print(best, sim_dict)
				if self.contexts:
					sim_dict['context'] = self.contexts[best]
				yield sim_dict
		similarity_list = similarity_dict[similarity_type]
		similarity_ranking_list = np.argsort(similarity_list, kind='stable', axis=-1)
		return [
			get_similarity_dict_generator(i, similarity_ranking[::-1])
			for i,similarity_ranking in enumerate(similarity_ranking_list)
		]
