from models.knowledge_extraction.couple_extractor import CoupleExtractor
from misc.jsonld_lib import *
import nltk
from nltk.corpus import framenet as fn

class CoupleAbstractor(CoupleExtractor):
	def abstract_couple_list(self, concept_dict_list):
		assert False, 'Not implemented'

class WordnetAbstractor(CoupleAbstractor):

	# def __init__(self, model_options):
	# 	nltk.download('punkt')
	# 	nltk.download('averaged_perceptron_tagger')
	# 	nltk.download('wordnet')
	# 	super().__init__(model_options)
		
	'''
	Firstly, the OPs sort of confused between relatedness and similarity, the distinction is fine but it's worth noting.

	Semantic relatedness measures how related two concepts are, using any kind of relation; algorithms:
	* Lexical Chains (Hirst and St-Onge, 1998)
	* Adapted/Extended Sense Overlaps algorithm (Banerjee and Pedersen, 2002/2003)
	* Vectorized Sense Overlaps (Patwardhan, 2003)
	
	Semantic similarity only considers the IS-A relation (i.e. hypernymy / hyponymy); algorithms:
	* Wu-Palmer measure (Wu and Palmer 1994)
	* Resnik measure (Resnik 1995)
	* Jiang-Conrath measure (Jiang and Conrath 1997)
	* Leacock-Chodorow measure (Leacock and Chodorow 1998)
	* Lin measure (Lin 1998)	
	Resnik, Jiang-Conrath and Lin measures are based on information content. The information content of a synset is -log the sum of all probabilities (computed from corpus frequencies) of all words in that synset (Resnik, 1995).
	Wu-Palmer and Leacock-Chodorow are based on path length; the similarity between two concepts /synsets is respective of the number of nodes along the shortest path between them.

	The list given above is inexhaustive, but historically, we can see that using similarity measure is sort of outdated since relatedness algorithms considers more relations and should theoretically give more disambiguating power to compare concepts.
	'''
	def abstract_couple_list(self, concept_dict_list):
		from pywsd import disambiguate
		from pywsd.similarity import max_similarity
		from pywsd.lesk import simple_lesk, adapted_lesk, cosine_lesk
	
		concept_dict_list = [
			self.get_couple_from_concept(concept_dict)
			if 'predicate' not in concept_dict else
			concept_dict
			for concept_dict in concept_dict_list
		]
		disambiguation_cache = {}
		for couple in concept_dict_list:
			sentence_text = couple['source']['sentence_text']
			if sentence_text not in disambiguation_cache:
				sentence_disambiguation = disambiguate(
					sentence_text,
					algorithm=cosine_lesk, 
					#similarity_option='wu-palmer',
				)
				disambiguation_cache[sentence_text] = {k.lower():v for k,v in sentence_disambiguation}
			synset_dict = disambiguation_cache[sentence_text]
			couple['concept']['synset'] = synset_dict.get(couple['concept']['text'], None)
			for concept_core_dict in couple['concept_core']:
				concept_core_dict['synset'] = synset_dict.get(concept_core_dict['text'], None)
			couple['predicate_core']['synset'] = synset_dict.get(couple['predicate_core']['text'], None)
		return concept_dict_list

class FramenetAbstractor(CoupleAbstractor):
	FRAME_GF_CACHE = {}
	FE_IN_LU_BY_DEP_CACHE = {}
	LU_LIST = [lu for lu in fn.lus() if lu.name.split('.')[1] == 'v']
	LU_KEY_LIST = [explode_concept_key(lu.name.split('.')[0]) for lu in LU_LIST]

	def __init__(self, model_options):
		# nltk.download('punkt')
		# nltk.download('averaged_perceptron_tagger')
		# nltk.download('framenet_v17')
		fn.propagate_semtypes()
		super().__init__(model_options)
		self.debug = model_options.get('debug', False)
		#self.with_frame_annotation = model_options.get('with_frame_annotation', True)
		self.lu_confidence_threshold = model_options.get('lu_confidence_threshold', 2/3)
		self.concept_confidence_threshold = model_options.get('concept_confidence_threshold', 1/2)

	@staticmethod
	def get_FE_and_GF_by_active_LU_annotation_list(lu_annotation_list):
		fe_dict = {}
		for annotation_dict in lu_annotation_list:
			is_passive_LU_embodiement = annotation_dict['is_passive_LU_embodiement']
			for fe_tuple, gf_tuple in zip(annotation_dict['frame_element'],annotation_dict['grammatical_function']):
				gf = gf_tuple[-1]
				#print(fe_tuple[-1], gf)
				if gf not in ['Ext','Obj']:
					continue
				if is_passive_LU_embodiement: # get gf in active form
					gf = 'Ext' if gf == 'Obj' else 'Obj'
				fe = fe_tuple[-1] # every lexical unit has only one frame, so we can use the frame element has unique key
				if fe not in fe_dict:
					fe_dict[fe] = set()
				fe_dict[fe].add(gf)
		return fe_dict

	def is_passive_LU_embodiement(self, text, lexical_unit_offset):
		for token in self.nlp(text):
			#print(token, token.idx)
			if token.idx == lexical_unit_offset[0]:
				predicate_dict = self.get_predicate_dict(token)
				if predicate_dict is not None:
					return self.is_passive(predicate_dict['predicate']['span'])
				break
		return False

	def get_LU_annotation_list(self, lu):
		return [
			{ # dict_keys(['cDate', 'status', 'ID', '_type', 'layer', '_ascii', 'Target', 'FE', 'GF', 'PT', 'Other', 'Sent', 'Verb', 'sent', 'text', 'LU', 'frame'])
				#'text': annotation['text'],
				#'id': annotation['ID'],
				#'lexical_unit': annotation['LU'].name,
				'frame_element': annotation['FE'][0],
				'grammatical_function': annotation['GF'],
				'phrase_type': annotation['PT'],
				#'lexical_unit_offset': annotation['Target'],
				'is_passive_LU_embodiement': self.is_passive_LU_embodiement(annotation['text'], annotation['Target'][0]),
			}
			for sub_corpus in lu.subCorpus
			for sentence in sub_corpus.sentence
			for annotation in sentence.annotationSet
			if annotation.get('GF',None) is not None
			and annotation.get('Target',None) is not None
			#and len(annotation['Target']) == 1 # Target 'rule out' has two separated offsets, even if it is a single target
		]

	def get_possible_FE_in_LU_by_dependency(self, lu, dependency):
		lu_name = lu.name
		cache_key = '{0}.{1}'.format(lu_name, dependency)
		if cache_key not in self.FE_IN_LU_BY_DEP_CACHE:
			if lu_name not in self.FRAME_GF_CACHE:
				lu_annotation_list = self.get_LU_annotation_list(lu)
				frame_element_active_grammatical_functions = self.get_FE_and_GF_by_active_LU_annotation_list(lu_annotation_list)
				self.FRAME_GF_CACHE[lu_name] = frame_element_active_grammatical_functions
			else:
				frame_element_active_grammatical_functions = self.FRAME_GF_CACHE[lu_name]
		
			related_frame = lu.frame
			if self.debug:
				print('Frame:', str(related_frame.name))

			abstract_couple_list = []
			for abstract_concept, fe in related_frame.FE.items():
				#if fe.coreType != 'Core':
				#	continue

				fe_name = fe.name
				active_grammatical_functions = frame_element_active_grammatical_functions.get(fe_name,None)
				if active_grammatical_functions is None:
					continue
				valid_gf = 'Obj' if 'obj' in dependency else 'Ext'
				if valid_gf not in active_grammatical_functions:
					continue

				semantic_type = fe.semType.name if fe.semType is not None else None
				abstract_couple_list.append({'frame_element':abstract_concept, 'semantic_type': semantic_type})
				if self.debug:
					print('Element:', {'fe': fe_name, 'active_gf': active_grammatical_functions})
				self.FE_IN_LU_BY_DEP_CACHE[cache_key] = abstract_couple_list
		else:
			abstract_couple_list = self.FE_IN_LU_BY_DEP_CACHE[cache_key]
		return abstract_couple_list

	@staticmethod
	def stringify_couple(concept, predicate, dependency):
		subject = concept if 'subj' in dependency else 'x'
		object = concept if 'obj' in dependency else 'x'
		str = f'{subject} {predicate} {object}'
		#str = str[0].upper() + str[1:] + '.'
		return str

	def abstract_couple(self, couple):
		if self.debug:
			print('###############################')
			print('Couple:', couple)
		is_passive_couple = couple['is_passive']
		couple_dependency = 'subj' if ('subj' in couple['dependency'] and not is_passive_couple) or ('obj' in couple['dependency'] and is_passive_couple) else 'obj'
		couple_predicate = couple['predicate']['lemma']
		fragment = self.stringify_couple(couple['concept']['lemma'], couple_predicate, couple_dependency)
		if self.debug:
			print('Fragment:', fragment)
			print('Is passive:', is_passive_couple)
		
		lu_argmax, lu_confidence = self.find_most_similar(couple_predicate, self.LU_KEY_LIST, cached=True)
		if lu_confidence < self.lu_confidence_threshold:
			return
		lu = self.LU_LIST[lu_argmax]
		lu_name = self.LU_KEY_LIST[lu_argmax]
		if self.debug:
			print('Most Similar LU:', lu_name)
			print('LU Confidence:', lu_confidence)

		# Find all possible frame elements
		abstract_couple_list = self.get_possible_FE_in_LU_by_dependency(lu, couple_dependency)
		if len(abstract_couple_list) == 0:
			return

		target_list = [
			self.stringify_couple(
				explode_concept_key(abstract_concept['frame_element']).lower().strip(), 
				couple_predicate, 
				couple_dependency
			)
			for abstract_concept in abstract_couple_list
		]
		
		concept_argmax, concept_confidence = self.find_most_similar(fragment, target_list, cached=True)
		if concept_confidence < self.concept_confidence_threshold:
			return
		most_similar_concept = abstract_couple_list[concept_argmax]
		if self.debug:
			print('Abstract Concept:', most_similar_concept)
			print('Confidence:', concept_confidence)

		# Update couples
		couple['concept_annotation'] = {
			#'embodiment': couple['concept']['text'],
			'confidence': concept_confidence,
		}
		couple['concept_annotation'].update(most_similar_concept)
		couple['predicate_annotation'] = {
			'lexical_unit': lu_name,
			'frame': lu.frame.name,
			'confidence': lu_confidence,
		}

	def abstract_couple_list(self, concept_dict_list):
		concept_dict_list = [
			self.get_couple_from_concept(concept_dict)
			if 'predicate' not in concept_dict else
			concept_dict
			for concept_dict in concept_dict_list
		]
		for couple in concept_dict_list:
			self.abstract_couple(couple)
		return concept_dict_list
