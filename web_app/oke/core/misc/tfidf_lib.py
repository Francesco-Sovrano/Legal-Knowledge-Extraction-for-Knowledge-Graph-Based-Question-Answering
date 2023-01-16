import gensim # for the tf-idf model
from gensim.test.utils import get_tmpfile

def build_tfidf(words_vector, very_big_corpus=False):
	# The code in the following block comes from: https://www.oreilly.com/learning/how-do-i-compare-document-similarity-using-python
	########################## START BLOCK ########################## 
	# Build word dictionary
	dictionary = gensim.corpora.Dictionary(words_vector)
	# Build the Bag-of-Words corpus from lemmatized documents
	corpus = [dictionary.doc2bow(gen_doc) for gen_doc in words_vector]
	# Build the tf-idf model from the corpus 
	tfidf_model = gensim.models.TfidfModel(corpus)
	# Build similarities cache
	# Similarity with cache into temporary file is slower than MatrixSimilarity but it can handle bigger corpus
	if very_big_corpus:
		tfidf_corpus_similarities = gensim.similarities.Similarity(get_tmpfile("index"), tfidf_model[corpus], num_features=len(dictionary))
	else:
		tfidf_corpus_similarities = gensim.similarities.MatrixSimilarity(tfidf_model[corpus], num_features=len(dictionary))
	########################## END BLOCK ##########################
	return dictionary, tfidf_model, tfidf_corpus_similarities

def get_query_tfidf_similarity(words_vector, dictionary, tfidf_model, tfidf_corpus_similarities):
	# Get query BoW (Bag of Words)
	query_bow = dictionary.doc2bow(words_vector)
	# Get query tf-idf
	query_tfidf = tfidf_model[query_bow]
	# Get query similarity vector
	return tfidf_corpus_similarities[query_tfidf]
