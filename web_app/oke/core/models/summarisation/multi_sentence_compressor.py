from models.model_manager import ModelManager
import models.summarisation.word_graph_summariser as wgs

class MultiSentenceCompressor(ModelManager):

	def __init__(self, model_options):
		super().__init__(model_options)
		self.disable_spacy_component = ["ner", "textcat", "neuralcoref"]

	def summarise_sentence_list(self, sentence_list, n=1, min_words_n=20, candidates_horizon=1000, ranking_strategy='boudin-morin', cached=True):
		taggedsentences=[
			' '.join((
				token.text+"/"+(token.tag_ if token.pos_ != 'PUNCT' else 'PUNCT')
				for token in doc
			)).strip()
			for doc in self.nlp([sentence])
		]
		# print(taggedsentences)
		
		# Create a word graph from the set of sentences with parameters :
		# - minimal number of words in the compression : 6
		# - language of the input sentences : en (english)
		# - POS tag for punctuation marks : PUNCT
		compresser = wgs.word_graph(taggedsentences, nb_words=min_words_n, lang='en', punct_tag="PUNCT")

		# Get the 50 best paths
		candidates = compresser.get_compression(candidates_horizon)

		if ranking_strategy == 'boudin-morin':
			# 2. Rerank compressions by keyphrases (Boudin and Morin's method)
			reranker = wgs.keyphrase_reranker(taggedsentences, candidates, lang = 'en')
			reranked_candidates = reranker.rerank_nbest_compressions()
			best_candidates = sorted(( # Normalize path score by path length 
				{
					'score': score,
					'text': ' '.join([u[0] for u in path])
				}
				for score, path in reranked_candidates
			), key=lambda x: x['score'], reverse=True)
		else: #if ranking_strategy == 'filippova':
			# 1. Rerank compressions by path length (Filippova's method)
			best_candidates = sorted(( # Normalize path score by path length 
				{
					'score': cummulative_score/len(path),
					'text': ' '.join([u[0] for u in path])
				}
				for cummulative_score, path in candidates
			), key=lambda x: x['score'], reverse=True)

		if len(best_candidates) == 0:
			best_candidates = [{'text':sentence}]
		elif n:
			best_candidates = best_candidates[:n]
		return tuple(map(lambda x:x['text'], best_candidates))
