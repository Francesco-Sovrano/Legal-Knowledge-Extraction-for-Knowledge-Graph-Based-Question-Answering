from models.classification.concept_classifier import ConceptClassifier
from more_itertools import unique_everseen
import os
import pandas as pd

class EuroVocClassifier(ConceptClassifier):
	EUROVOC_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)),'data/eurovoc.csv')
	DEFAULT_OPTIONS = {
		'spacy_model': 'en_core_web_md',
		'tf_model':'USE_Transformer',
		'with_semantic_shifting':True,
		'with_centered_similarity':True,
		'tfidf_importance': 3/4,
		'default_similarity_threshold': 0.8,
	}

	def __init__(self, model_options=DEFAULT_OPTIONS):
		super().__init__(model_options)
		eurovoc_df = pd.read_csv(self.EUROVOC_PATH, sep=';')
		unique_term_list = tuple(unique_everseen(eurovoc_df['TERMS (PT-NPT)'].values))
		concept_description_dict = {t:[t] for t in unique_term_list}
		self.set_concept_description_dict(concept_description_dict)

	def get_concept_dict(self, concept_counter_dict={}, similarity_threshold=None, with_numbers=True, size=1):
		return super().get_concept_dict(concept_counter_dict=concept_counter_dict, similarity_threshold=similarity_threshold, with_numbers=with_numbers, size=size)
