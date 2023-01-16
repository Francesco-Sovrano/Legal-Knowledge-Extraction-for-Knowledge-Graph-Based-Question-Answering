from misc.doc_reader import DocParser
from models.knowledge_extraction.couple_extractor import CoupleExtractor
from models.knowledge_extraction.couple_abstractor import WordnetAbstractor, FramenetAbstractor
from models.classification.concept_classifier import ConceptClassifier
from misc.graph_builder import build_edge_dict, get_biggest_connected_graph, get_subject_set, get_concept_description_dict
from misc.jsonld_lib import *

import re
from more_itertools import unique_everseen
from collections import Counter
import json
import nltk
from nltk.corpus import stopwords

class KnowledgeGraphBuilder(CoupleExtractor):
	
	def set_documents_path(self, doc_path, remove_stopwords=True, remove_pronouns=True, remove_numbers=True):
		doc_parser = DocParser().set_documents_path(doc_path)
		self.build_couple_list(doc_parser, remove_stopwords, remove_pronouns, remove_numbers)
		return self

	def set_document_list(self, doc_list, remove_stopwords=True, remove_pronouns=True, remove_numbers=True):
		doc_parser = DocParser().set_document_list(doc_list)
		self.build_couple_list(doc_parser, remove_stopwords, remove_pronouns, remove_numbers)
		return self

	def set_content_list(self, content_list, remove_stopwords=True, remove_pronouns=True, remove_numbers=True):
		doc_parser = DocParser().set_document_list(content_list)
		self.build_couple_list(doc_parser, remove_stopwords, remove_pronouns, remove_numbers)
		return self

	def build_couple_list(self, doc_parser: DocParser, remove_stopwords, remove_pronouns, remove_numbers):
		couple_iter = self.get_couple_list(doc_parser)
		if remove_pronouns: # Ignore pronouns
			couple_iter = filter(lambda c: c['concept_core'][-1]['lemma'] not in ['-pron-',''], couple_iter)
		if remove_stopwords: # Ignore stowords
			couple_iter = filter(lambda c: not c['concept_core'][-1]['lemma'] in stopwords.words('english'), couple_iter)
		if remove_numbers: # Ignore concepts containing digits
			couple_iter = filter(lambda c: re.search(r'\d', c['concept']['text']) is None, couple_iter)
		if not remove_pronouns: # Remove empty strings
			couple_iter = list(couple_iter)
			for couple in couple_iter:
				'''
				if 'obj' in couple['dependency']:
					print(couple['predicate']['lemma'], couple['concept']['lemma'])
				else:
					print(couple['concept']['lemma'], couple['predicate']['lemma'])
				'''
				for concept_core_dict in couple['concept_core']:
					if concept_core_dict['lemma'] in ['-pron-','']:
						concept_core_dict['lemma'] = couple['concept']['text']
				if couple['concept']['lemma'] in ['-pron-','']:
					couple['concept']['lemma'] = couple['concept']['text']
		self.couple_list = list(filter(lambda x: len(x)>0, couple_iter))
		self.graph_list = list(doc_parser.get_graph_iter())

	@staticmethod
	def is_valid_syntagm(syntagm, max_syntagma_length):
		if not max_syntagma_length:
			return True
		return syntagm.count(' ') < max_syntagma_length

	@staticmethod
	def get_family_concept_set(graph, concept_set, max_depth=None, current_depth=0):
		if len(concept_set) == 0:
			return set()
		sub_concept_set = get_subject_set(filter(lambda x: x[1]==SUBCLASSOF_PREDICATE and x[0] not in concept_set and x[-1] in concept_set, graph))
		current_depth +=1
		if len(sub_concept_set) == 0 or current_depth==max_depth:
			return set(concept_set)
		return KnowledgeGraphBuilder.get_family_concept_set(graph, concept_set.union(sub_concept_set), max_depth, current_depth)

	@staticmethod
	def get_uri_from_concept_dict(s):
		return re.sub(r'\s', '', f"{CONCEPT_PREFIX}{s['lemma'].replace(' ','_')}", flags=re.UNICODE)

	def get_edge_list(self, couple_list, add_subclasses=False, use_framenet_fe=False, use_wordnet=False, add_source=False, add_label=False, to_rdf=False, lemmatize_label=False):
		# Build triples dict
		triple_dict = {}
		for couple in couple_list:
			triple_predicate_id = (
				self.get_concept_dict_uid(couple['predicate']), 
				self.get_source_dict_uid(couple['source'])
			)
			triple_key = 'subj' if 'subj' in couple['dependency'] else 'obj'
			triple_predicate_dict = triple_dict.get(triple_predicate_id, None)
			if triple_predicate_dict is None:
			# 	triple_predicate_dict = triple_dict[triple_predicate_id] = {'subj':[], 'pred':couple, 'obj':[]}
			# current_syntagm_list = triple_predicate_dict[triple_key]
			# current_syntagm_list.append(couple)
				triple_predicate_dict = triple_dict[triple_predicate_id] = {'subj':{}, 'pred':couple, 'obj':{}}
			current_syntagm_dict = triple_predicate_dict[triple_key]
			core_key = self.get_concept_dict_uid(couple['concept_core'][-1])
			# print(triple_predicate_id, core_key, couple['concept']['lemma'])
			# Keep the longest concept_dicts
			if core_key not in current_syntagm_dict or self.get_concept_dict_size(couple['concept']) > self.get_concept_dict_size(current_syntagm_dict[core_key]['concept']):
				current_syntagm_dict[core_key] = couple
		# Build edge list
		edge_list = [
			(subj, triple['pred'], obj) # Every triple has to have a subject and an object
			for triple in triple_dict.values()
			for subj in triple['subj'].values()
			for obj in triple['obj'].values()
		]
		# Format triples
		get_concept_label = (lambda c: c['lemma']) if lemmatize_label else (lambda c: c['text'])
		get_concept_id = self.get_uri_from_concept_dict if to_rdf else get_concept_label
		get_concept_doc_idx = lambda c: c['idx']
		source_dict = {}
		formatted_edge_list = []
		for s,p,o in edge_list:
			s_cp, p_cp, o_cp = s['concept'], p['predicate'], o['concept']
			s_id, p_id, o_id = get_concept_id(s_cp), get_concept_id(p_cp), get_concept_id(o_cp)
			s_lb, p_lb, o_lb = get_concept_label(s_cp), get_concept_label(p_cp), get_concept_label(o_cp)
			formatted_edge_list.append((s_id, p_id, o_id))
			if to_rdf and add_label:
				formatted_edge_list.extend((
					(s_id, HAS_LABEL_PREDICATE, s_lb),
					# (s_id, HAS_IDX_PREDICATE, get_concept_doc_idx(s_cp)),
					(p_id, HAS_LABEL_PREDICATE, p_lb),
					# (p_id, HAS_IDX_PREDICATE, get_concept_doc_idx(p_cp)),
					(o_id, HAS_LABEL_PREDICATE, o_lb),
					# (o_id, HAS_IDX_PREDICATE, get_concept_doc_idx(o_cp)),
				))
			sentence = p['source']['paragraph_text']
			doc = p['source']['doc']
			source_key = (doc,sentence)
			source_uri = source_dict.get(source_key,None)
			if source_uri is None:
				annotation = p['source'].get('annotation', None)
				if annotation and annotation.get('root', None):
					source_uri = annotation['root']
				else:
					source_uri = f'{ANONYMOUS_PREFIX}{urify(doc)}_source{len(source_dict)}'
				source_dict[source_key] = source_uri
				if add_source:
					formatted_edge_list.extend((
						(source_uri, CONTENT_PREDICATE, sentence),
						# (source_uri, HAS_IDX_PREDICATE, p['source']['sent_idx']),
						(source_uri, DOC_ID_PREDICATE, DOC_PREFIX+doc),
					))
				# add annotations
				if annotation:
					formatted_edge_list.extend(annotation['content'])
			# connect triples to sources
			if add_source:
				formatted_edge_list.extend((
					(s_id, HAS_SOURCE_PREDICATE, source_uri),
					(p_id, HAS_SOURCE_PREDICATE, source_uri),
					(o_id, HAS_SOURCE_PREDICATE, source_uri),
				))
		# Abstract triples
		if use_wordnet or use_framenet_fe or add_subclasses:
			valid_couple_list = list(unique_everseen(
				list(edge[0] for edge in edge_list)+list(edge[-1] for edge in edge_list), 
				key=self.get_couple_uid
			))
			# add wordnet triples
			if use_wordnet:
				wordnet_abstractor = WordnetAbstractor(self.model_options)
				valid_couple_list = wordnet_abstractor.abstract_couple_list(valid_couple_list)
				for couple in valid_couple_list:
					c,p = couple['concept'], couple['predicate']
					c_syn,p_syn = c.get('synset',None), p.get('synset',None)
					if c_syn is not None:
						formatted_edge_list.append((get_concept_id(c), IN_SYNSET_PREDICATE, f"{WORDNET_PREFIX}{c_syn.name()}"))
					if p_syn is not None:
						formatted_edge_list.append((get_concept_id(p), IN_SYNSET_PREDICATE, f"{WORDNET_PREFIX}{p_syn.name()}"))
			# add framenet triples
			if use_framenet_fe:
				framenet_abstractor = FramenetAbstractor(self.model_options)
				valid_couple_list = framenet_abstractor.abstract_couple_list(valid_couple_list)
				for couple in valid_couple_list:
					concept_annotation = couple.get('concept_annotation', None)
					if concept_annotation is None:
						continue
					semantic_type = concept_annotation['semantic_type']
					frame_element = 'fne:{0}_{1}'.format(couple['predicate_annotation']['frame'],concept_annotation['frame_element'])
					if semantic_type is not None:
						#formatted_edge_list.append((lemmatized_syntagm, 'has_type', semantic_type))
						formatted_edge_list.append((frame_element, HAS_TYPE_PREDICATE, 'fns:'+semantic_type))
					# Frame Element is always different from None
					formatted_edge_list.append((frame_element, CAN_BE_PREDICATE, get_concept_id(couple['concept'])))
			# add subclasses
			if add_subclasses:
				subclass_predicate = SUBCLASSOF_PREDICATE if to_rdf else ('be' if lemmatize_label else 'is a')
				formatted_edge_list.extend(filter(
					lambda x: x[0]!=x[-1], # remove autoreferential relations
					(
						(get_concept_id(couple['concept_core'][e]), subclass_predicate, get_concept_id(couple['concept_core'][e+1]))
						for couple in valid_couple_list
						for e in range(len(couple['concept_core'])-1)
					)
				))
				if to_rdf and add_label:
					formatted_edge_list.extend((
						(get_concept_id(concept_core), HAS_LABEL_PREDICATE, get_concept_label(concept_core))
						for couple in valid_couple_list
						for concept_core in couple['concept_core']
					))
				if add_source:
					formatted_edge_list.extend((
						(get_concept_id(concept_core), HAS_SOURCE_PREDICATE, source_uri)
						for couple in valid_couple_list
						for concept_core in couple['concept_core']
					))
		# remove duplicates
		formatted_edge_list = list(unique_everseen(formatted_edge_list))
		return formatted_edge_list

	def get_graph_hinge(self, source_graph, source_valid_concept_filter_fn, target_graph, target_valid_concept_filter_fn):
		# Get concept_description_dicts
		source_concept_description_dict = get_concept_description_dict(
			graph= source_graph, 
			label_predicate= HAS_LABEL_PREDICATE, 
			valid_concept_filter_fn= source_valid_concept_filter_fn,
		)
		target_concept_description_dict = get_concept_description_dict(
			graph= target_graph, 
			label_predicate= HAS_LABEL_PREDICATE, 
			valid_concept_filter_fn= target_valid_concept_filter_fn,
		)
		# Build concept classifier using the target_graph
		concept_classifier = ConceptClassifier(self.model_options).set_concept_description_dict(target_concept_description_dict)
		# Classify source graph's labels
		source_uri_list, source_label_list = zip(*[
			(uri,label)
			for uri, label_list in source_concept_description_dict.items()
			for label in label_list
		])
		similarity_dict_generator_list = concept_classifier.classify(
			source_label_list, 
			'weighted', 
			tfidf_importance=0
		)
		# Build the graph hinge
		graph_hinge = []
		for source_concept_uri, similarity_dict_generator in zip(source_uri_list, similarity_dict_generator_list):
			similarity_dict = next(similarity_dict_generator,None)
			if not similarity_dict:
				continue
			target_concept_uri = similarity_dict['id']
			if target_concept_uri != source_concept_uri:
				graph_hinge.append((target_concept_uri, IN_SYNSET_PREDICATE, source_concept_uri))
		return graph_hinge

	def build(self, max_syntagma_length=None, add_subclasses=False, use_framenet_fe=False, use_wordnet=False, add_source=False, add_label=False, to_rdf=True, lemmatize_label=True):
		couple_list = [
			couple
			for couple in self.couple_list
			if self.is_valid_syntagm(couple['concept']['lemma'], max_syntagma_length)
		]
		edge_list = self.get_edge_list(
			couple_list, 
			add_subclasses=add_subclasses, 
			use_framenet_fe=use_framenet_fe, 
			use_wordnet=use_wordnet, 
			add_source=add_source, 
			add_label=add_label, 
			to_rdf=to_rdf, 
			lemmatize_label=lemmatize_label
		)
		external_graph = []
		for graph in self.graph_list:
			external_graph += list(graph) + self.get_graph_hinge(
				graph, 
				lambda x: not (x[0].startswith(DOC_PREFIX) or x[0].startswith(ANONYMOUS_PREFIX)), 
				edge_list, 
				lambda x: '{obj}' in x[1]
			)
		# print(json.dumps(external_graph, indent=4))
		return edge_list + external_graph

