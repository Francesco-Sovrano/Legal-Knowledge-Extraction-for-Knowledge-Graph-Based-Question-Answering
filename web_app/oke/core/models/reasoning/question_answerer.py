from misc.doc_reader import DocParser
from models.model_manager import ModelManager
from models.knowledge_extraction.ontology_builder import OntologyBuilder
from models.classification.concept_classifier import ConceptClassifier
from models.classification.sentence_classifier import SentenceClassifier
from models.summarisation.neural_sentence_summariser import NeuralSentenceSummariser
from misc.adjacency_matrix import AdjacencyMatrix
from misc.graph_builder import get_root_set, get_concept_set, get_predicate_set, get_object_set, get_connected_graph_list, get_ancestors, filter_graph_by_root_set, tuplefy, get_concept_description_dict, get_betweenness_centrality
from misc.levenshtein_lib import remove_similar_labels, labels_are_similar
from misc.jsonld_lib import *

from collections import Counter
import re
import time
import json
from more_itertools import unique_everseen
import itertools
import wikipedia
from nltk.corpus import wordnet as wn
from nltk.corpus import brown
from nltk import FreqDist

word_frequency_distribution = FreqDist(i.lower() for i in brown.words())
is_common_word = lambda w: word_frequency_distribution.freq(w) >= 1e-4
singlefy = lambda s: s.strip().replace("\n"," ")#.capitalize()

class QuestionAnswerer(ModelManager):

	def __init__(self, graph, model_options, query_concept_classifier_options, answer_classifier_options, answer_summariser_options):
		# nltk.download('wordnet')
		super().__init__(model_options)
		self.disable_spacy_component = ["ner", "textcat", "neuralcoref"]
		self.log = model_options.get('log',False)

		self.adjacency_matrix = AdjacencyMatrix(
			graph, 
			equivalence_relation_set=set([IN_SYNSET_PREDICATE]),
			is_sorted=True,
		)
		self.adjacency_matrix_no_equivalence = AdjacencyMatrix(
			graph, 
			equivalence_relation_set=set(),
			is_sorted=True,
		)

		# self.subclass_dict = QuestionAnswerer.get_predicate_dict(get_predicate_dict, SUBCLASSOF_PREDICATE)
		self.content_dict = QuestionAnswerer.get_predicate_dict(self.adjacency_matrix, CONTENT_PREDICATE, singlefy)
		self.source_dict = QuestionAnswerer.get_predicate_dict(self.adjacency_matrix, HAS_SOURCE_PREDICATE)
		self.label_dict = QuestionAnswerer.get_predicate_dict(self.adjacency_matrix, HAS_LABEL_PREDICATE, singlefy)

		self.content_dict_no_equiv = QuestionAnswerer.get_predicate_dict(self.adjacency_matrix_no_equivalence, CONTENT_PREDICATE, singlefy)
		self.source_dict_no_equiv = QuestionAnswerer.get_predicate_dict(self.adjacency_matrix_no_equivalence, HAS_SOURCE_PREDICATE)
		self.label_dict_no_equiv = QuestionAnswerer.get_predicate_dict(self.adjacency_matrix_no_equivalence, HAS_LABEL_PREDICATE, singlefy)
		if self.log:
			print("Building concept classifier..")
		self.concept_classifier = ConceptClassifier(query_concept_classifier_options).set_concept_description_dict(
			get_concept_description_dict(
				graph= graph, 
				label_predicate= HAS_LABEL_PREDICATE, 
				valid_concept_filter_fn= lambda x: '{obj}' in x[1]
			)
		)
		# Betweenness centrality quantifies the number of times a node acts as a bridge along the shortest path between two other nodes.		
		betweenness_centrality = get_betweenness_centrality(filter(lambda x: '{obj}' in x[1], graph))
		betweenness_centrality = dict(filter(lambda x:x[-1]>0 and not is_common_word(explode_concept_key(x[0]).lower()), betweenness_centrality.items()))
		if self.log:
			print("Important concepts:", json.dumps(betweenness_centrality, indent=4))
		self.important_concept_classifier = ConceptClassifier(query_concept_classifier_options).set_concept_description_dict(
			{
				c: self.label_dict[c]
				for c in betweenness_centrality
			}
		)
		if self.log:
			print("Concept classifier built")
		# Sentence classification
		self.sentence_classifier = SentenceClassifier(answer_classifier_options)
		# Summarisation
		self.sentence_summariser = NeuralSentenceSummariser(answer_summariser_options)

	@staticmethod
	def get_predicate_dict(adjacency_matrix, predicate, manipulation_fn=lambda x: x): # Build labels dict
		predicate_dict = {}
		for s in adjacency_matrix.get_nodes():
			for _,o in filter(lambda x: x[0]==predicate, adjacency_matrix.get_outcoming_edges_matrix(s)):
				plist = predicate_dict.get(s, None)
				if not plist:
					plist = predicate_dict[s] = []
				plist.append(manipulation_fn(o))
		for k,v in predicate_dict.items():
			v.sort()
		return predicate_dict

	@staticmethod
	def get_question_answer_dict_quality(question_answer_dict, top=5):
		return {
			question: {
				# 'confidence': {
				# 	'best': answers[0]['confidence'],
				# 	'top_mean': sum(map(lambda x: x['confidence'], answers[:top]))/top,
				# },
				# 'syntactic_similarity': {
				# 	'best': answers[0]['syntactic_similarity'],
				# 	'top_mean': sum(map(lambda x: x['syntactic_similarity'], answers[:top]))/top,
				# },
				# 'semantic_similarity': {
				# 	'best': answers[0]['semantic_similarity'],
				# 	'top_mean': sum(map(lambda x: x['semantic_similarity'], answers[:top]))/top,
				# },
				'valid_answers_count': len(answers),
				'syntactic_similarity': answers[0]['syntactic_similarity'],
				'semantic_similarity': answers[0]['semantic_similarity'],
			}
			for question,answers in question_answer_dict.items()
		}

	def get_label(self, concept_uri, explode_if_none=True):
		if concept_uri in self.label_dict:
			return self.label_dict[concept_uri][0]
		if concept_uri.startswith(WORDNET_PREFIX):
			return explode_concept_key(wn.synset(concept_uri[3:]).lemmas()[0].name())
		return explode_concept_key(concept_uri) if explode_if_none else ''

	def get_sub_graph(self, uri, depth=None, predicate_filter_fn=lambda x: x != SUBCLASSOF_PREDICATE and '{obj}' not in x):
		uri_set = self.adjacency_matrix.get_predicate_chain(set([uri]), direction_set=['out'], depth=depth, predicate_filter_fn=predicate_filter_fn)
		return [
			(s,p,o)
			for s in uri_set
			for p,o in self.adjacency_matrix_no_equivalence.get_outcoming_edges_matrix(s)
		]

	def get_concept_graph(self, concept_uri, add_external_definitions=False, include_super_concepts_graph=False, include_sub_concepts_graph=False, consider_incoming_relations=False, depth=None, filter_fn=lambda x: x):
		concept_set = set([concept_uri])
		expanded_concept_set = set(concept_set)
		# Get sub-classes
		if include_sub_concepts_graph:
			sub_concept_set = self.adjacency_matrix.get_predicate_chain(
				concept_set = concept_set, 
				predicate_filter_fn = lambda x: x == SUBCLASSOF_PREDICATE, 
				direction_set = ['in'],
				depth = depth,
			)
			expanded_concept_set |= sub_concept_set
		# Get super-classes
		if include_super_concepts_graph:
			super_concept_set = self.adjacency_matrix.get_predicate_chain(
				concept_set = concept_set, 
				predicate_filter_fn = lambda x: x == SUBCLASSOF_PREDICATE, 
				direction_set = ['out'],
				depth = depth,
			)
			expanded_concept_set |= super_concept_set
		# expanded_concept_set = sorted(expanded_concept_set) # this would improve caching, later on
		# Add outcoming relations to concept graph
		expanded_concept_graph = [
			(s,p,o)
			for s in expanded_concept_set
			for p,o in self.adjacency_matrix_no_equivalence.get_outcoming_edges_matrix(s)
		]
		# Add incoming relations to concept graph
		if consider_incoming_relations:
			expanded_concept_graph += [
				(s,p,o)
				for o in expanded_concept_set
				for p,s in self.adjacency_matrix_no_equivalence.get_incoming_edges_matrix(o)
			]
		# print(concept_uri, json.dumps(expanded_concept_graph, indent=4))
		expanded_concept_graph = list(filter(filter_fn, expanded_concept_graph))
		# Add external definitions
		if add_external_definitions:
			# Add wordnet's definition
			for equivalent_concept_uri in filter(lambda x: x.startswith(WORDNET_PREFIX), self.adjacency_matrix.equivalence_matrix.get(concept_uri,[])):
				synset = wn.synset(equivalent_concept_uri[3:]) # remove string WORDNET_PREFIX, 3 chars
				definition = synset.definition()
				expanded_concept_graph.append((concept_uri,HAS_DEFINITION_PREDICATE,definition))
			# Add wikipedia's (short) definition
			# try:
			# 	definition = wikipedia.summary(
			# 		self.get_label(concept_uri), 
			# 		sentences=1, # short
			# 		chars=0,
			# 		auto_suggest=True, 
			# 		redirect=True
			# 	)
			# 	expanded_concept_graph.append((concept_uri,HAS_DEFINITION_PREDICATE,definition))
			# except:
			# 	pass
		return expanded_concept_graph
	
	def get_sourced_graph_from_concept_graph(self, concept_graph, concept_uri, add_clustered_triples=False):
		# Get labeled triples
		label_graph = self.get_labeled_graph_from_concept_graph(concept_graph, concept_uri)
		# Add clustered triples
		if add_clustered_triples:
			label_graph += self.find_couple_clusters_in_labeled_graph(label_graph)
		# Add source to triples
		return self.get_sourced_graph_from_labeled_graph(label_graph)

	def get_sourced_graph_from_labeled_graph(self, label_graph):
		sourced_natural_language_triples_set = []
		def extract_sourced_graph(label_graph, str_fn):
			result = []
			for labeled_triple, original_triple in label_graph:
				naturalized_triple = str_fn(labeled_triple)
				# print(naturalized_triple, labeled_triple)
				if not naturalized_triple:
					continue
				s,p,o = original_triple
				context_set = set(self.source_dict_no_equiv.get(p,[])).intersection(self.source_dict_no_equiv.get(s,[])).intersection(self.source_dict_no_equiv.get(o,[]))
				# print(s,p,o)
				# print(self.source_dict.get(s,[]))
				# print(self.source_dict.get(p,[]))
				# print(self.source_dict.get(o,[]))
				# print(context_set)
				if not context_set:
					context_set = [None]
				result += [
					(
						naturalized_triple, 
						self.content_dict[source_id][0] if source_id else naturalized_triple, # source_label
						original_triple,
						source_id if source_id else None, # source_id
					)
					for source_id in context_set
				]
			return result
		sourced_natural_language_triples_set += extract_sourced_graph(label_graph, get_string_from_triple)
		sourced_natural_language_triples_set += extract_sourced_graph(label_graph, lambda x: x[0])
		sourced_natural_language_triples_set += extract_sourced_graph(label_graph, lambda x: x[-1])
		sourced_natural_language_triples_set = list(unique_everseen(sourced_natural_language_triples_set))
		return sourced_natural_language_triples_set

	def get_labeled_graph_from_concept_graph(self, concept_graph, concept_uri):
		# Get labeled triples
		label_graph = []
		for original_triple in concept_graph:
			s,p,o = original_triple
			if s == o:
				continue
			p_is_subclassof = p == SUBCLASSOF_PREDICATE
			if p_is_subclassof: # remove redundant triples not directly concerning the concept
				if o!=concept_uri and s!=concept_uri:
					continue
			for label_p in self.label_dict_no_equiv.get(p,[p]):
				label_p_context = set(self.source_dict_no_equiv.get(label_p,[])) # get label sources
				for label_s in self.label_dict_no_equiv.get(s,[s]):
					if label_p_context: # triple with sources
						label_s_context = set(self.source_dict_no_equiv.get(label_s,[])) # get label sources
						label_context = label_s_context.intersection(label_p_context)
						if not label_context: # these two labels do not appear together, skip
							continue
					# print(set(label_s_context).intersection(label_p_context))
					for label_o in self.label_dict_no_equiv.get(o,[o]):
						if label_p_context: # triple with sources
							label_o_context = set(self.source_dict_no_equiv.get(label_o,[])) # get label sources
							if not label_context.intersection(label_o_context): # these labels do not appear together, skip
								continue
						if p_is_subclassof and labels_are_similar(label_s,label_o):
							continue
						labeled_triple = (label_s,label_p,label_o)
						label_graph.append((labeled_triple, original_triple))
		return label_graph

	def find_couple_clusters_in_labeled_graph(self, label_graph):
		sp_dict = {}
		po_dict = {}
		couple_clusters = []
		for labeled_triple, original_triple in label_graph:
			sp_key = (tuple(labeled_triple[:2]),tuple(original_triple[:2]))
			o_list = sp_dict.get(sp_key, None)
			if not o_list:
				o_list = sp_dict[sp_key] = []
			o_list.append((labeled_triple[-1],original_triple[-1]))
			po_key = (tuple(labeled_triple[1:]),tuple(original_triple[1:]))
			s_list = po_dict.get(po_key, None)
			if not s_list:
				s_list = po_dict[po_key] = []
			s_list.append((labeled_triple[0],original_triple[0]))

		for sp_key,o_list in sp_dict.items():
			if len(o_list) <= 1:
				continue
			labeled_sp, original_sp = sp_key
			o_list = unique_everseen(sorted(o_list, key=lambda x: x[0]), key=lambda x: x[-1])
			o_list = remove_similar_labels(list(o_list))
			labeled_o, original_o = zip(*o_list)
			couple_clusters.append((
				(*labeled_sp, tuple(labeled_o)),
				(*original_sp, tuple(original_o))
			))
		for po_key,s_list in po_dict.items():
			if len(s_list) <= 1:
				continue
			labeled_po, original_po = po_key
			s_list = unique_everseen(sorted(s_list, key=lambda x: x[0]), key=lambda x: x[-1])
			s_list = remove_similar_labels(list(s_list))
			labeled_s, original_s = zip(*s_list)
			couple_clusters.append((
				(tuple(labeled_s), *labeled_po),
				(tuple(original_s), *original_po)
			))
		return couple_clusters

	def find_answers_in_concept_graph(self, query_list, concept_uri, question_answer_dict, answer_pertinence_threshold=0.55, add_external_definitions=False, add_clustered_triples=False, include_super_concepts_graph=False, include_sub_concepts_graph=False, consider_incoming_relations=False, tfidf_importance=None):
		def get_formatted_answer(answer):
			triple, source_uri = answer['id']
			sentence = answer['context']
			# if triple[1] == HAS_DEFINITION_PREDICATE:
			# 	print(sentence)
			return {
				'abstract': answer['doc'],
				'confidence': answer['similarity'],
				'syntactic_similarity': answer['syntactic_similarity'],
				'semantic_similarity': answer['semantic_similarity'],
				'annotation': self.get_sub_graph(source_uri) if source_uri else None,
				'sentence': sentence, 
				'triple': triple, 
				'source_id': source_uri if source_uri else sentence, 
			}

		concept_graph = self.get_concept_graph(
			concept_uri=concept_uri, 
			add_external_definitions=add_external_definitions, 
			include_super_concepts_graph=include_super_concepts_graph, 
			include_sub_concepts_graph=include_sub_concepts_graph, 
			consider_incoming_relations=consider_incoming_relations,
			filter_fn=lambda x: '{obj}' in x[1],
		)
		if self.log:
			print('######## Concept Graph ########')
			print(concept_uri, len(concept_graph), json.dumps(concept_graph, indent=4))
		# Extract sourced triples
		sourced_natural_language_triples_set = self.get_sourced_graph_from_concept_graph(concept_graph, concept_uri, add_clustered_triples=add_clustered_triples)
		if len(sourced_natural_language_triples_set) <= 0:
			if self.log:
				print('Missing:', concept_uri)
			return
		# sourced_natural_language_triples_set.sort(key=str) # only for better summary caching
		# Setup Sentence Classifier
		abstract_iter, context_iter, original_triple_iter, source_id_iter = zip(*sourced_natural_language_triples_set)
		id_doc_iter = tuple(zip(
			zip(original_triple_iter, source_id_iter), # id
			abstract_iter # doc
		))
		self.sentence_classifier.set_documents(id_doc_iter, tuple(context_iter))
		# Classify
		classification_dict_list = self.sentence_classifier.classify(
			query_list=query_list, 
			similarity_type='weighted', 
			similarity_threshold=answer_pertinence_threshold, 
			as_question=True, 
			tfidf_importance=tfidf_importance
		)
		# Format Answers
		for question, answer_iter in zip(query_list, classification_dict_list):
			answer_list = sorted(answer_iter, key=lambda x: x['similarity'], reverse=True)
			answer_list = tuple(unique_everseen(answer_list, key=lambda x: x["id"]))
			if len(answer_list) == 0:
				continue
			formatted_answer_list = question_answer_dict.get(question,None)
			if not formatted_answer_list:
				formatted_answer_list = question_answer_dict[question] = []
			formatted_answer_list += (
				get_formatted_answer(answer)
				for answer in answer_list
			)
			# formatted_answer_list.sort(key=lambda x: x['confidence'], reverse=True)
		return question_answer_dict

	def get_subclass_replacer(self, superclass):
		superclass_set = set([superclass])
		subclass_set = self.adjacency_matrix.get_predicate_chain(
			concept_set = superclass_set, 
			predicate_filter_fn = lambda x: x == SUBCLASSOF_PREDICATE, 
			direction_set = ['in'],
			depth = 1, # get only first level subclasses
		).difference(superclass_set)
		# print(subclass_set)
		exploded_superclass = explode_concept_key(superclass).strip().lower()
		exploded_subclass_iter = map(lambda x: explode_concept_key(x).strip().lower(), subclass_set)
		exploded_subclass_iter = filter(lambda x: x and not x.startswith(exploded_superclass), exploded_subclass_iter)
		exploded_subclass_list = sorted(exploded_subclass_iter, key=lambda x:len(x), reverse=True)
		# print(exploded_subclass_list)
		if len(exploded_subclass_list) == 0:
			return None
		# print(exploded_superclass, exploded_subclass_list)
		subclass_regexp = re.compile('|'.join(exploded_subclass_list))
		return lambda x,triple: re.sub(subclass_regexp, exploded_superclass, x) if triple[1]!=SUBCLASSOF_PREDICATE else x

################################################################################################################################################

	def ask(self, question_list, query_concept_similarity_threshold=0.55, answer_pertinence_threshold=0.55, with_numbers=True, remove_stopwords=False, lemmatized=False, keep_the_n_most_similar_concepts=1, add_external_definitions=False, add_clustered_triples=False, include_super_concepts_graph=True, include_sub_concepts_graph=True, consider_incoming_relations=True, tfidf_importance=None):
		# set consider_incoming_relations to False with concept-centred generic questions (e.g. what is it?), otherwise the answers won't be the sought ones
		doc_parser = DocParser().set_content_list(question_list)
		concepts_dict = self.concept_classifier.get_concept_dict(
			doc_parser,
			similarity_threshold=query_concept_similarity_threshold, 
			with_numbers=with_numbers, 
			remove_stopwords=remove_stopwords, 
			lemmatized=lemmatized
		)
		if self.log:
			print('######## Concepts Dict ########')
			print(len(concepts_dict))
		# For every aligned concept, extract from the ontology all the incoming and outgoing triples, thus building a partial graph (a view).
		question_answer_dict = {}
		for concept_label, concept_count_dict in concepts_dict.items():
			for concept_similarity_dict in itertools.islice(unique_everseen(concept_count_dict["similar_to"], key=lambda x: x["id"]), min(1,keep_the_n_most_similar_concepts)):
				concept_uri = concept_similarity_dict["id"]
				concept_query_list = [
					sent_dict["paragraph_text"]
					for sent_dict in concept_count_dict["source_list"]
				]
				self.find_answers_in_concept_graph(
					query_list= concept_query_list, 
					concept_uri= concept_uri, 
					question_answer_dict= question_answer_dict, 
					answer_pertinence_threshold= answer_pertinence_threshold,
					add_external_definitions= add_external_definitions,
					add_clustered_triples= add_clustered_triples,
					include_super_concepts_graph= include_super_concepts_graph, 
					include_sub_concepts_graph= include_sub_concepts_graph, 
					consider_incoming_relations= consider_incoming_relations,
					tfidf_importance= tfidf_importance,
				)
		# Sort answers
		for question, formatted_answer_list in question_answer_dict.items():
			question_answer_dict[question] = list(unique_everseen(
				sorted(
					formatted_answer_list, 
					key=lambda x: x['confidence'], reverse=True
				), 
				key=lambda x: x["sentence"]
			))
		return question_answer_dict

	def get_concept_overview(self, query_template_list, concept_uri, concept_label=None, answer_pertinence_threshold=0.3, add_external_definitions=True, add_clustered_triples=True, include_super_concepts_graph=True, include_sub_concepts_graph=True, consider_incoming_relations=True, tfidf_importance=None):
		# set consider_incoming_relations to False with concept-centred generic questions (e.g. what is it?), otherwise the answers won't be the sought ones
		if not concept_label:
			concept_label = self.get_label(concept_uri)
		question_answer_dict = {}
		self.find_answers_in_concept_graph(
			query_list= tuple(map(lambda x:x.replace('{concept}',concept_label), query_template_list)), 
			concept_uri= concept_uri, 
			question_answer_dict= question_answer_dict, 
			answer_pertinence_threshold= answer_pertinence_threshold,
			add_external_definitions= add_external_definitions,
			add_clustered_triples= add_clustered_triples,
			include_super_concepts_graph= include_super_concepts_graph, 
			include_sub_concepts_graph= include_sub_concepts_graph, 
			consider_incoming_relations= consider_incoming_relations,
			tfidf_importance= tfidf_importance,
		)
		return question_answer_dict

	def summarise_question_answer_dict(self, question_answer_dict, ignore_non_grounded_answers=True, use_abstracts=False, summary_horizon=None, tree_arity=5, cut_factor=2, depth=None, similarity_threshold=0.3, remove_duplicates=True, min_size_for_summarising=None):
		# print(json.dumps(question_answer_dict, indent=4))
		get_sentence = lambda x: x["abstract" if use_abstracts else 'sentence']
		if remove_duplicates:
			processed_sentence_set = set()
		question_summarised_answer_dict = {}
		for question, answer_list in question_answer_dict.items():
			answer_iter = iter(answer_list)
			if ignore_non_grounded_answers:
				answer_iter = filter(lambda x: x['annotation'], answer_iter)
			if remove_duplicates:
				answer_iter = filter(lambda x: get_sentence(x) not in processed_sentence_set, answer_iter)
			answer_iter = unique_everseen(answer_iter, key=get_sentence)
			if summary_horizon:
				answer_list = tuple(itertools.islice(answer_iter, summary_horizon))
			else:
				answer_list = tuple(answer_iter)
			sentence_iter = map(get_sentence, answer_list)
			# sentence_iter = map(self.sentence_summariser.sentify, sentence_iter)
			sentence_list = list(sentence_iter)
			if use_abstracts:
				sentence_list = remove_similar_labels(sentence_list, similarity_threshold)
			integration_map = dict(zip(sentence_list,answer_list))
			summary_tree_list = self.sentence_summariser.summarise_sentence_list(sentence_list, tree_arity=tree_arity, cut_factor=cut_factor, depth=depth, min_size=min_size_for_summarising)
			self.sentence_summariser.integrate_summary_tree_list(integration_map, summary_tree_list)
			if summary_tree_list:
				if len(summary_tree_list) == 1:
					question_summarised_answer_dict[question] = summary_tree_list[0]
				else:
					# self.sentence_classifier.set_documents(tuple(enumerate(map(lambda x: x['summary'], summary_tree_list))))
					# # Classify
					# classification_list = self.sentence_classifier.classify(query_list=[question], similarity_type='weighted', similarity_threshold=0, as_question=True)[0]
					# sorted_summary_tree_list = [
					# 	summary_tree_list[i]
					# 	for i in map(lambda x: x['id'], classification_list)
					# ]
					question_summarised_answer_dict[question] = {
						'summary': summary_tree_list[0]['summary'],
						# 'children': summary_tree_list[1:] + summary_tree_list[:1]
						'children': summary_tree_list[0]['children'] + summary_tree_list[1:]
					}
			else:
				question_summarised_answer_dict[question] = {}
			###############################
			# for a in answer_list:
			# 	a['summary'] = a['sentence']
			# question_summarised_answer_dict[question] = {
			# 	'summary': self.sentence_summariser.summarise_sentence(' '.join(sentence_list))[0],
			# 	'children': answer_list
			# }
			if remove_duplicates:
				processed_sentence_set |= set(sentence_list)
		return question_summarised_answer_dict

	def annotate_question_summary_tree(self, question_summary_tree, similarity_threshold=0.8, max_concepts_per_alignment=1):
		if not question_summary_tree:
			return []
		def extract_sentence_list_from_tree(summary_tree):
			if not summary_tree:
				return []
			children = summary_tree.get('children',None)
			if not children:
				# label_list = [summary_tree['sentence']]
				# if 'summary' in summary_tree:
				# 	label_list.append(summary_tree['summary'])
				# return label_list
				return [summary_tree['sentence']] # extractive summaries contain the same words in the sentences
			label_list = []
			for c in children:
				label_list += extract_sentence_list_from_tree(c)
			return label_list
		sentence_list = sum(map(lambda x: extract_sentence_list_from_tree(x), question_summary_tree.values()), [])
		sentence_list = tuple(unique_everseen(sentence_list))
		return self.important_concept_classifier.annotate(
			DocParser().set_content_list(sentence_list), 
			similarity_threshold=similarity_threshold, 
			max_concepts_per_alignment=max_concepts_per_alignment
		)

	def annotate_taxonomical_view(self, taxonomical_view, similarity_threshold=0.8, max_concepts_per_alignment=1):
		if not taxonomical_view:
			return []
		sentence_iter = map(lambda y: y[-1], filter(lambda x: not is_url(x[-1]), taxonomical_view))
		return self.important_concept_classifier.annotate(
			DocParser().set_content_list(list(sentence_iter)), 
			similarity_threshold=similarity_threshold, 
			max_concepts_per_alignment=max_concepts_per_alignment
		)
		
	def get_taxonomical_view(self, concept_uri, depth=None):
		concept_set = set((concept_uri,))
		if depth != 0:
			sub_concept_set = self.adjacency_matrix.get_predicate_chain(
				concept_set = concept_set, 
				predicate_filter_fn = lambda x: x == SUBCLASSOF_PREDICATE, 
				direction_set = ['in'],
				depth = depth,
			)
			super_concept_set = self.adjacency_matrix.get_predicate_chain(
				concept_set = concept_set, 
				predicate_filter_fn = lambda x: x == SUBCLASSOF_PREDICATE, 
				direction_set = ['out'],
				depth = depth,
			)
			concept_set |= sub_concept_set
			concept_set |= super_concept_set
		# Add subclassof relations
		taxonomical_view = set(
			(s,p,o)
			for s in concept_set
			for p,o in self.adjacency_matrix_no_equivalence.get_outcoming_edges_matrix(s)
			if p == SUBCLASSOF_PREDICATE
		).union(
			(s,p,o)
			for o in concept_set
			for p,s in self.adjacency_matrix_no_equivalence.get_incoming_edges_matrix(o)
			if p == SUBCLASSOF_PREDICATE
		)
		taxonomical_view = list(taxonomical_view)
		taxonomy_concept_set = get_concept_set(taxonomical_view).union(concept_set)
		# Add labels
		taxonomical_view += (
			(concept, HAS_LABEL_PREDICATE, self.get_label(concept, explode_if_none=False))
			for concept in taxonomy_concept_set
		)
		# for concept in taxonomy_concept_set:
		# 	if not concept.startswith(WORDNET_PREFIX):
		# 		print(concept, self.label_dict[concept])
		# Add sources
		taxonomical_view += (
			(concept, HAS_SOURCE_PREDICATE, source)
			for concept in taxonomy_concept_set
			for source in self.source_dict.get(concept,())
		)
		for concept in taxonomy_concept_set:
			for source in self.source_dict.get(concept,()):
				taxonomical_view += self.get_sub_graph(source)
		# Add wordnet definitions
		taxonomical_view += (
			(concept, HAS_DEFINITION_PREDICATE, wn.synset(concept[3:]).definition())
			for concept in filter(lambda x: x.startswith(WORDNET_PREFIX), taxonomy_concept_set)
		)
		# Add definitions
		taxonomical_view += unique_everseen(
			(concept_uri,p,o)
			for p,o in self.adjacency_matrix_no_equivalence.get_outcoming_edges_matrix(concept_uri)
			if p == HAS_DEFINITION_PREDICATE
		)
		# Add types
		sub_types_set = self.adjacency_matrix.get_predicate_chain(
			concept_set = concept_set, 
			predicate_filter_fn = lambda x: x == HAS_TYPE_PREDICATE, 
			direction_set = ['out'],
			depth = 0,
		)
		super_types_set = self.adjacency_matrix.get_predicate_chain(
			concept_set = concept_set, 
			predicate_filter_fn = lambda x: x == HAS_TYPE_PREDICATE, 
			direction_set = ['in'],
			depth = 0,
		)
		taxonomical_view += (
			(concept_uri,HAS_TYPE_PREDICATE,o)
			for o in sub_types_set - concept_set
		)
		taxonomical_view += (
			(s,HAS_TYPE_PREDICATE,concept_uri)
			for s in super_types_set - concept_set
		)
		taxonomical_view += unique_everseen(
			(s, HAS_LABEL_PREDICATE, self.get_label(s, explode_if_none=False))
			for s in (super_types_set | sub_types_set) - concept_set
		)
		taxonomical_view = filter(lambda x: x[0] and x[1] and x[2], taxonomical_view)
		# print(taxonomical_view)
		return list(taxonomical_view)
	
	def cache_whole_graph(self, sentence_classifier_cache, concept_classifier_cache, sentence_summariser_cache):
		self.sentence_classifier.load_cache(sentence_classifier_cache)
		self.concept_classifier.load_cache(concept_classifier_cache)
		self.important_concept_classifier.load_cache(concept_classifier_cache)
		self.sentence_summariser.load_cache(sentence_summariser_cache)

		is_valid_concept = lambda x: isinstance(x, str) and len(x)>3 and x[2]==':' and '{obj}' not in x
		
		clean_root_set = get_root_set(self.adjacency_matrix.graph)
		clean_root_set = set(filter(is_valid_concept, clean_root_set))

		clique_iter = self.adjacency_matrix.SCC()
		clique_iter = map(lambda x: tuple(filter(is_valid_concept,x)), clique_iter)
		clique_iter = filter(lambda x: len(x)>1, clique_iter)
		clique_root_set = set(map(lambda x: x[0], clique_iter))

		valid_root_set = clique_root_set.union(clean_root_set)
		# valid_root_set = ['my:obligation', 'my:law'] + list(valid_root_set)
		if self.log:
			print(f'There are {len(clean_root_set)} clean roots and {len(valid_root_set)-len(clean_root_set)} clique roots.')
		concept_set = set()
		for i,concept_uri in enumerate(valid_root_set):
			progress = 100*(i/len(valid_root_set))
			#### Get concept graph ####
			if self.log:
				t = time.time()
				print('Building concept graph..')
			concept_graph = self.get_concept_graph(
				concept_uri=concept_uri, 
				add_external_definitions=False, 
				include_super_concepts_graph=True, 
				include_sub_concepts_graph=True, 
				consider_incoming_relations=True,
				filter_fn=lambda x: '{obj}' in x[1],
			)
			if self.log:
				print('######## Concept Graph ########')
				# print(f'{progress}%', concept_uri, len(concept_graph), json.dumps(concept_graph, indent=4))
				print(f'{progress}%', concept_uri, len(concept_graph))
			# Extract sourced triples
			sourced_natural_language_triples_set = self.get_sourced_graph_from_concept_graph(concept_graph, concept_uri, add_clustered_triples=True)
			# sourced_natural_language_triples_set.sort(key=str) # only for better summary caching
			if self.log:
				print(f'Concept graph built in {time.time()-t}')
			if len(sourced_natural_language_triples_set) <= 0:
				if self.log:
					print('Missing:', concept_uri)
				continue
			#### Cache pertinence generator ####
			if self.log:
				t = time.time()
				print('Generating pertinence cache..')
			abstract_iter, context_iter, original_triple_iter, source_id_iter = zip(*sourced_natural_language_triples_set)
			self.sentence_classifier.run_tf_embedding(zip(abstract_iter,context_iter), as_question=False)
			if self.log:
				print(f'Pertinence cache generated in {time.time()-t}')
			##############
			concept_set |= get_concept_set(concept_graph)
		#### Cache sentence classifier ####	
		self.sentence_classifier.store_cache(sentence_classifier_cache)
		#### Cache concept classifier ####
		if self.log:
			t = time.time()
			print('Generating sentence annotation cache..')
		sentence_iter = (
			label
			for source in unique_everseen(sum(self.source_dict.values(),[]))
			for label in self.content_dict.get(source,())
		)
		self.important_concept_classifier.annotate(
			DocParser().set_content_list(tuple(unique_everseen(sentence_iter))),
			similarity_threshold=0, 			
		)
		if self.log:
			print(f'Sentence annotation cache generated in {time.time()-t}')
		self.important_concept_classifier.store_cache(concept_classifier_cache)
		if self.log:
			t = time.time()
			print('Generating summary cache..')
		source_set = unique_everseen((
			source
			for source_list in self.source_dict.values()
			for source in source_list
		))
		summarised_sources = tuple(map(self.sentence_summariser.summarise_sentence, source_set))
		self.sentence_summariser.store_cache(sentence_summariser_cache)
		if self.log:
			print(f'Summary cache generated in {time.time()-t}')
