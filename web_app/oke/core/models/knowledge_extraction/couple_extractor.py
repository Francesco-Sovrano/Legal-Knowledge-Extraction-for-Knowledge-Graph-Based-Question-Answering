from misc.doc_reader import DocParser
from models.knowledge_extraction.concept_extractor import ConceptExtractor as CE
import re
# import json

class CoupleExtractor(CE):
	# PREDICATE_COMPONENT = [ # https://universaldependencies.org/u/dep/all.html
	# 	'prt',		# particle
	# 	'neg',		# negation modifier
	# 	'auxpass',	# auxiliary (passive)
	# 	'advcl',	# adverbial clause modifier
	# 	'agent',	# agent
	# 	'acomp',	# adjectival complement
	# 	'xcomp',	# open clausal complement
	# 	'pcomp',	# complement of preposition
	# 	'ccomp',	# clausal complement
	# 	'prep',		# prepositional modifier
	# ]
	# HIDDEN_PREDICATE_COMPONENT = [
	# 	'aux',		# auxiliaries
	# 	'mark', 	# marker - https://universaldependencies.org/docs/en/dep/mark.html
	# 	'advmod',	# adverbial modifier
	# 	'cc',		# coordinating conjunction
	# ]
	# PREDICATE_REGEXP = re.compile('|'.join(PREDICATE_COMPONENT+HIDDEN_PREDICATE_COMPONENT))
	CC_FILTER_FN = lambda x: x.pos_=='PUNCT' or x.dep_=='cc' # punctuation and conjunctions
	
	@staticmethod
	def is_passive(span): # return true if the sentence is passive - at the moment a sentence is assumed to be passive if it has an auxpass verb
		for token in span:
			if CE.get_token_dependency(token) == "auxpass":
				return True
		return False

	@staticmethod
	def is_verbal(span): # return true if the sentence is passive - at the moment a sentence is assumed to be passive if it has an auxpass verb
		for token in span:
			if token.pos_ == "VERB":
				return True
		return False

	@staticmethod
	def is_at_core(concept):
		concept_span = concept['concept']['span']
		return len(concept_span)==1 and len(concept['concept_core'])==1 and concept['concept_core'][0]['span'][0] == concept_span[0]

	@staticmethod
	def get_couple_uid(couple):
		return (CE.get_concept_dict_uid(couple['concept']), CE.get_concept_dict_uid(couple['predicate']), couple['dependency'])

	@staticmethod
	def is_in_predicate(x,predicate_span):
		return x.idx > predicate_span[0].idx and x.idx < predicate_span[-1].idx

	@staticmethod
	def trim_noise(token_list):
		forbidden_dep = set(['cc', 'prep', 'punct'])
		return CE.trim(token_list, lambda x: CE.get_token_dependency(x) in forbidden_dep)

	@staticmethod
	def expand_predicate_core(predicate_set, subj_obj_set): # enrich predicate set with details, adding hidden related concepts (n-ary relations)
		hidden_related_concept_set = set((
			hidden_related_concept
			for predicate_element in predicate_set
			for hidden_related_concept in CE.get_token_descendants(predicate_element, lambda x: x not in subj_obj_set and x not in predicate_set)
		))
		return predicate_set | hidden_related_concept_set #| hidden_related_concept_detail_set

	@staticmethod
	def get_grammatical_connection(core, other_core, core_set): # can be one per core in core_set
		subj_obj_set = set((core,other_core))
		# Search for indirect connections with other concepts
		core_super_set = set(core.ancestors) # do not use CE.get_token_ancestors here, it messes up with conjunctions
		core_super_set.add(core)
		other_core_super_set = set(other_core.ancestors)
		other_core_super_set.add(other_core)
		inter = core_super_set.intersection(other_core_super_set)
		if len(inter)==0: # core and other_core are not connected, continue
			return None
		# get paths connecting cores to each other
		core_path_to_inter,core_junction = CE.find_path_to_closest_in_set(core,inter)
		if core_junction:
			core_path_to_inter.add(core_junction)
		core_path_to_inter = core_path_to_inter.difference(subj_obj_set)
		if len(core_path_to_inter.intersection(core_set)) > 0: # avoid jumps
			return None
		other_core_path_to_inter,other_core_junction = CE.find_path_to_closest_in_set(other_core,inter)
		if other_core_junction:
			other_core_path_to_inter.add(other_core_junction)
		other_core_path_to_inter = other_core_path_to_inter.difference(subj_obj_set)
		if len(other_core_path_to_inter.intersection(core_set)) > 0: # avoid jumps
			return None
		# Get predicate set
		predicate_core_set = core_path_to_inter.union(other_core_path_to_inter)
		if len(predicate_core_set)==0:
			return None
		# Enrich predicate set with details, adding hidden related concepts (n-ary relations)
		predicate_set = CoupleExtractor.expand_predicate_core(predicate_core_set, subj_obj_set=subj_obj_set)
		# Add missing conjunctions
		if core in other_core.children:
			predicate_set |= set(filter(CoupleExtractor.CC_FILTER_FN, other_core.children))
		elif other_core in core.children:
			predicate_set |= set(filter(CoupleExtractor.CC_FILTER_FN, core.children))
		# Get predicate spans
		predicate_span = sorted(predicate_set, key=lambda x: x.idx)
		predicate_core_span = sorted(predicate_core_set, key=lambda x: x.idx)
		# # Remove consecutive punctuations
		# non_consecutive_puncts = set([',',';'])
		# predicate_span = [
		# 	v 
		# 	for i, v in enumerate(predicate_span) 
		# 	if i == 0 
		# 	or v.pos_ != 'PUNCT' 
		# 	or v.pos_ != predicate_span[i-1].pos_ 
		# 	or v.text not in non_consecutive_puncts 
		# 	or predicate_span[i-1].text not in non_consecutive_puncts
		# ]
		return {
			'predicate_span':predicate_span,
			'predicate_core_span': predicate_core_span,
			'cores_couple': (core,other_core),
		}

	@staticmethod
	def grammatical_connections_to_graph(caotic_triple_list):
		triple_list = []
		for triple_dict in caotic_triple_list:
			predicate_span = triple_dict['predicate_span']
			assert len(predicate_span) > 0, f'predicate_span is empty'
			predicate_core_span = triple_dict['predicate_core_span']
			assert len(predicate_core_span) > 0, f'predicate_core_span is empty'
			core, other_core = triple_dict['cores_couple']
			core_is_obj = re.search(CE.OBJ_REGEXP, CE.get_token_dependency(core)) is not None
			other_core_is_obj = re.search(CE.OBJ_REGEXP, CE.get_token_dependency(other_core)) is not None
			core_is_subj = re.search(CE.SUBJ_REGEXP, CE.get_token_dependency(core)) is not None
			other_core_is_subj = re.search(CE.SUBJ_REGEXP, CE.get_token_dependency(other_core)) is not None
			# Handle ambiguous dependencies
			# ambiguous_dep = core_is_obj != other_core_is_subj or core_is_subj != other_core_is_obj or core_is_obj == core_is_subj # or other_core_is_obj == other_core_is_subj
			if core_is_obj!=other_core_is_obj:
				if core_is_obj:
					subj = other_core
					obj = core
				else:
					subj = core
					obj = other_core
			elif core_is_subj!=other_core_is_subj:
				if core_is_subj:
					subj = core
					obj = other_core
				else:
					subj = other_core
					obj = core
			else: # position-based decision
				if core.idx < other_core.idx:
					subj = core
					obj = other_core
				else:
					subj = other_core
					obj = core
			triple = {
				'subj': subj,
				'obj': obj,
				'predicate_span': predicate_span, # add predicate components
				# 'predicate_set': set(predicate_span),
				'predicate_core_span': predicate_core_span,
				# 'predicate_core_set': set(predicate_core_span),
			}
			# print(triple)
			triple_list.append(triple)
		return triple_list

	@staticmethod
	def get_core_predicate_dict(core_set):
		# find the paths that connect the core concepts each other
		core_list = list(core_set)
		grammatical_connection_list = list(filter(lambda x: x is not None,(
			CoupleExtractor.get_grammatical_connection(core, other_core, core_set)
			for i,core in enumerate(core_list)
			for other_core in core_list[i+1:]
		)))
		# print(grammatical_connection_list)
		directed_concept_graph = CoupleExtractor.grammatical_connections_to_graph(grammatical_connection_list)
		# print(directed_concept_graph)
		# create core predicate dict
		core_predicate_dict = {}		
		for edge in directed_concept_graph:
			predicate_span = edge['predicate_span']
			subj = edge['subj']
			obj = edge['obj']
			# print(subj,predicate_span,obj)

			get_concept_dict = lambda span: CoupleExtractor.get_concept_dict_from_span(span)#, hidden_dep_list=CoupleExtractor.HIDDEN_PREDICATE_COMPONENT)
			# get predicate_dict
			predicate_dict = get_concept_dict(predicate_span)
			# templatize predicate_dict
			triple_span = predicate_span + [subj,obj]
			triple_span = CoupleExtractor.trim_noise(sorted(triple_span, key=lambda x:x.idx))
			subj_pos = triple_span.index(subj)
			obj_pos = triple_span.index(obj)
			if subj_pos < obj_pos:
				left_pivot = subj_pos
				right_pivot = obj_pos
				left_is_subj = True
			else:
				left_pivot = obj_pos
				right_pivot = subj_pos
				left_is_subj = False
			templatized_lemma = []
			templatized_text = []
			if left_pivot > 0:
				left_pdict = get_concept_dict(triple_span[:left_pivot])
				templatized_lemma.append(left_pdict['lemma'])
				templatized_text.append(left_pdict['text'])
			templatized_lemma.append('{subj}' if left_is_subj else '{obj}')
			templatized_text.append('{subj}' if left_is_subj else '{obj}')
			if right_pivot > left_pivot+1:
				middle_pdict = get_concept_dict(triple_span[left_pivot+1:right_pivot])
				templatized_lemma.append(middle_pdict['lemma'])
				templatized_text.append(middle_pdict['text'])
			templatized_lemma.append('{obj}' if left_is_subj else '{subj}')
			templatized_text.append('{obj}' if left_is_subj else '{subj}')
			if right_pivot < len(triple_span)-1:
				right_pdict = get_concept_dict(triple_span[right_pivot+1:])
				templatized_lemma.append(right_pdict['lemma'])
				templatized_text.append(right_pdict['text'])
			predicate_dict['text'] = ' '.join(templatized_text)
			predicate_dict['lemma'] = ' '.join(templatized_lemma)
			# get predicate_core_dict
			predicate_core_dict = get_concept_dict(edge['predicate_core_span'])

			# populate core_predicate_dict
			if subj not in core_predicate_dict:
				core_predicate_dict[subj] = []
			core_predicate_dict[subj].append({
				'dependency': 'subj', 
				'predicate': predicate_dict,
				'predicate_core': predicate_core_dict,
				# 'missing_passivant': subj.i > predicate_span[0].i,
				# 'related_concepts_count': related_concepts_count, # if related_concepts_count > 2, then n-ary relation
			})
			if obj not in core_predicate_dict:
				core_predicate_dict[obj] = []
			core_predicate_dict[obj].append({
				'dependency': 'obj', 
				'predicate': predicate_dict,
				'predicate_core': predicate_core_dict,
				# 'missing_passivant': False,
				# 'related_concepts_count': related_concepts_count, # if related_concepts_count > 2, then n-ary relation
			})
		return core_predicate_dict

	def get_couple_list(self, doc_parser: DocParser):
		concept_list = self.get_concept_list(doc_parser)
		core_concept_dict = {}
		for concept in concept_list:
			core = concept['concept_core'][-1]['span'][0]
			if core not in core_concept_dict:
				core_concept_dict[core] = []
			core_concept_dict[core].append(concept)
		# print(core_concept_dict)

		core_predicate_dict = self.get_core_predicate_dict(set(core_concept_dict.keys()))
		# print(core_predicate_dict)
		couple_list = []
		for core, core_concepts in core_concept_dict.items():
			if core not in core_predicate_dict:
				# print(f'"{core}" not in core_predicate_dict')
				continue
			for concept_dict in core_concepts:
				concept_span_set = set(concept_dict['concept']['span'])
				is_at_core = self.is_at_core(concept_dict)
				for predicate_dict in core_predicate_dict[core]:
					if len(concept_span_set.intersection(predicate_dict['predicate']['span'])) > 0:
						# print(f'Discarding concept "{concept_dict["concept"]["text"]}", because it intersects its predicate: "{predicate_dict["predicate"]["text"]}".')
						continue
					couple_dict = {
						'is_at_core': is_at_core,
					}
					couple_dict.update(concept_dict)
					couple_dict.update(predicate_dict)
					couple_list.append(couple_dict)
		# print([(c['dependency'],c['concept']['text'],c['predicate']['text']) for c in couple_list])
		return couple_list
