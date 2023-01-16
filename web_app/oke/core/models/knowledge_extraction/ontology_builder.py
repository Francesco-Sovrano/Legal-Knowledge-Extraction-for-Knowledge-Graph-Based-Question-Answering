from models.knowledge_extraction.knowledge_graph_builder import KnowledgeGraphBuilder
from models.knowledge_extraction.lattice_builder import ActiveActionTypingLatticeBuilder
from misc.graph_builder import get_root_set, get_concept_set, get_predicate_set, get_object_set, get_connected_graph_list, get_ancestors, filter_graph_by_root_set, tuplefy
from misc.graph_builder import save_graph
from misc.jsonld_lib import *

from more_itertools import unique_everseen
import re

import nltk
from nltk.corpus import wordnet as wn

class OntologyBuilder(KnowledgeGraphBuilder):
	WORDNET_TO_PATTERN_MAP = {
		'pro:RoleInTime': ['causal_agent\.n\.01'],
		# 'foaf:Person': ['person\.n\.01'],
		'foaf:Organization': ['organization\.n\.01'],
		'ti:TimeInterval': ['time_period\.n\.01'],
		'pro:InformationObject': ['information','written_communication'],
		'pro:Place': ['location\.n\.01'],
		# 'owl:Thing': ['object'],
		# 'pro:Role': ['role\.n\.01'],
		'pwo:Action': ['action\.n\.01'],
		# 'pwo:Workflow': ['process\.n\.06'],
		'pro:Obligation': ['obligation\.n'],
	}

	KNOWN_ONTO_PATTERN_EDGE_LIST = [
		# Agent-Role pattern
		('pro:RoleInTime', SUBCLASSOF_PREDICATE, 'pro:Role'),
		('lkif:Agent', 'pro:holdsRoleInTime', 'pro:RoleInTime'),
		('pro:RoleInTime', 'pro:withRole', 'pro:Role'),
		('pro:RoleInTime', 'tvc:atTime', 'ti:TimeInterval'),
		('pro:RoleInTime', 'pro:relatesToDocument', 'foaf:Document'),
		('pro:RoleInTime', 'pro:relatesToPerson', 'foaf:Person'),
		('pro:RoleInTime', 'pro:relatesToOrganization', 'foaf:Organization'),
		# TVC pattern
		('pro:ValueInTime', 'pro:withValue', 'owl:Thing'),
		('owl:Thing', 'pro:hasValue', 'pro:ValueInTime'),
		('pro:ValueInTime', 'pro:withContext', 'owl:Thing'),
		('pro:ValueInTime', 'tvc:atTime', 'pro:Instant'),
		('pro:ValueInTime', 'pro:atTime', 'ti:TimeInterval'),
		('owl:Thing', CAN_BE_PREDICATE, 'lkif:Jurisdiction'),
		('owl:Thing', CAN_BE_PREDICATE, 'pro:Place'),
		# Process pattern
		('pwo:WorkflowExecution', 'pwo:executes', 'pwo:Workflow'),
		('pwo:WorkflowExecution', 'pwo:involvesAction', 'pwo:Action'),
		('pwo:Workflow', 'pwo:hasStep', 'pwo:Step'),
		('pwo:Workflow', 'pwo:hasFirstStep', 'pwo:Step'),
		('pwo:Step', 'pwo:hasNextStep', 'pwo:Step'),
		('pwo:Step', 'pwo:produces', 'owl:Thing'),
		('pwo:Step', 'pwo:needs', 'owl:Thing'),
		('pwo:Action', 'tisit:atTime', 'ti:TimeInterval'),
		('pwo:Step', 'taskex:isExecutedIn', 'owl:Thing'),
		('pwo:Step', 'parameter:hasParameter', 'time:DurationDescription'),
		# Deontic Ontology
		('pro:DeonticSpecification', 'pro:hasPointed', 'pro:AuxiliaryParty'),
		('pro:DeonticSpecification', 'pro:isHeld', 'pro:Interval'),
		('pro:Bearer', 'pro:setsUp', 'pro:DeonticSpecification'),
		('pro:DeonticSpecification', 'pro:componentOf', 'pro:LegalRule'),
		('pro:Permission', SUBCLASSOF_PREDICATE, 'pro:DeonticSpecification'),
		('pro:Right', SUBCLASSOF_PREDICATE, 'pro:DeonticSpecification'),
		('pro:Permission', 'pro:foundedOn', 'pro:Right'),
		('pro:Compliance', SUBCLASSOF_PREDICATE, 'pro:DeonticSpecification'),
		('pro:Obligation', SUBCLASSOF_PREDICATE, 'pro:DeonticSpecification'),
		('pro:Compliance', 'pro:complies', 'pro:Obligation'),
		('pro:Right', 'pro:generates', 'pro:Obligation'),
		('pro:Violation', SUBCLASSOF_PREDICATE, 'pro:DeonticSpecification'),
		('pro:Prohibition', SUBCLASSOF_PREDICATE, 'pro:DeonticSpecification'),
		('pro:Violation', 'pro:foundedOn', 'pro:Obligation'),
		('pro:Violation', 'pro:foundedOn', 'pro:Prohibition'),
		('pro:PrescriptiveRule', SUBCLASSOF_PREDICATE, 'pro:LegalRule'),
		('pro:ConstitutiveRule', SUBCLASSOF_PREDICATE, 'pro:LegalRule'),
		('pro:Penalty', 'pro:repairs', 'pro:PrescriptiveRule'),
		# PrOnto Ontology
		('pwo:Action', 'pro:generateRevision', 'allot:FRBRExpression'),
		('pwo:Action', 'pro:isActedBy', 'lkif:Agent'),
		('pwo:Action', 'taskex:executesTask', 'pwo:Step'),
		('pwo:Workflow', 'pwo:hasStep', 'pwo:Step'),
		('pwo:Step', 'pwo:needs', 'pro:InformationObject'),
		('pwo:Step', 'pro:hasStepType', 'pro:StepType'),
		('pwo:Step', 'pwo:produces', 'pro:InformationObject'),
		('pwo:Step', 'pwo:needs', 'pro:InformationObject'),
		('pwo:Step', 'pro:commits', 'pro:LegalRule'),
		('pro:LegalRule', SUBCLASSOF_PREDICATE, 'pro:PrescriptiveRule'),
		('pro:LegalRule', SUBCLASSOF_PREDICATE, 'pro:ConstitutiveRule'),
		('pro:DeonticSpecification', 'pro:componentOf', 'pro:LegalRule'),
		('pro:DeonticSpecification', 'pro:isHeld', 'ti:TimeInterval'),
		('pro:ValueInTimeAndContext', 'tvc:atTime', 'ti:TimeInterval'),
		('pro:ValueInTimeAndContext', 'tvc:withinContext', 'pro:Place'),
		('pro:ValueInTimeAndContext', 'tvc:withinContext', 'lkif:Jurisdiction'),
		('pro:ValueInTimeAndContext', 'tvc:withValue', 'pro:Value'),
	]
	
	def __init__(self, model_options):
		# nltk.download('wordnet')
		self.max_syntagma_length = model_options.get('max_syntagma_length', 5)
		self.add_source = model_options.get('add_source', False)
		self.add_label = model_options.get('add_label', True)
		self.lemmatize_label = model_options.get('lemmatize_label', False)
		self.lattice_builder = ActiveActionTypingLatticeBuilder(templatize=False)
		super().__init__(model_options)

	@staticmethod
	def print_graph(edge_iter, file_name):
		edge_iter = filter(lambda x: '{obj}' not in x[1], edge_iter)
		edge_list = list(edge_iter)
		print(f'Printing {file_name} with {len(edge_list)} triples')
		save_graph(edge_list, file_name, max(min(256,len(edge_list)/2),32))

	def build_edge_list(self):
		edge_list = super().build(
			max_syntagma_length=self.max_syntagma_length, 
			add_subclasses=True, 
			use_wordnet=True,
			add_source=self.add_source, 
			add_label=self.add_label,
			lemmatize_label=self.lemmatize_label,
			to_rdf=True,
		)
		edge_list = tuplefy(edge_list)
		return edge_list

	@staticmethod
	def get_hypernym_edge_list(concept_set):
		hyper = lambda s: s.hypernyms()
		# hypo = lambda s: s.hyponyms()
		concept_hypernyms_dict = {}
		for concept in concept_set:
			if not isinstance(concept, str) or not concept.startswith(WORDNET_PREFIX):
				continue
			synset = wn.synset(concept[3:]) # remove string WORDNET_PREFIX, 3 chars
			concept_hypernyms_dict[concept] = set(synset.closure(hyper)).union((synset,))

		hypernym_edge_list = [
			(concept, SUBCLASSOF_PREDICATE, WORDNET_PREFIX+hypernym.name())
			for concept, hypernym_set in concept_hypernyms_dict.items()
			for hypernym in hypernym_set
		]
		return hypernym_edge_list

	def extract_minimal_taxonomy(self, main_edge_list):
		concept_set = get_concept_set(main_edge_list)
		hypernym_edge_list = self.get_hypernym_edge_list(concept_set)
		hypernym_edge_list = self.lattice_builder.build_lattice(hypernym_edge_list)
		return list(unique_everseen(hypernym_edge_list))

	@staticmethod
	def format_taxonomy(hypernym_edge_list):
		# hypernym_edge_list to RDF
		taxonomy_edge_list = []
		for subj_list, pred_list, obj_list in hypernym_edge_list:
			for subj in subj_list:
				for _,pred in pred_list:
					for obj in obj_list:
						taxonomy_edge_list.append((pred,SUBCLASSOF_PREDICATE,subj))
						if obj != pred:
							taxonomy_edge_list.append((obj,SUBCLASSOF_PREDICATE,pred))
		return taxonomy_edge_list

	def connect_taxonomy_to_patterns(self, hypernym_edge_list):
		# get sorted concept set by moving parents on top of children
		hypernym_concept_set = get_concept_set(hypernym_edge_list)
		hypernym_concept_ancestors_list = [
			(c, get_ancestors(c, hypernym_edge_list))
			for c in hypernym_concept_set
		]
		hypernym_concept_ancestors_list.sort(key=lambda x: len(x[-1]))

		pattern_edge_list = []
		type_set_dict = {}
		for root,_ in hypernym_concept_ancestors_list:
			for key,value_list in self.WORDNET_TO_PATTERN_MAP.items():
				for value in value_list:
					if re.search(re.compile(value), root) is not None:
						pattern_edge_list.append((root,'rdf:type',key))
						if key not in type_set_dict:
							type_set_dict[key] = set()
						type_set_dict[key].add(root)

		for root,root_ancestors in hypernym_concept_ancestors_list:
			root_intension = set(
				predicate 
				for fcc in self.lattice_builder.formal_concept_context_list 
				for _,predicate in fcc.intension([root.strip()])
			)
			for intension in root_intension:
				for key,value_list in self.WORDNET_TO_PATTERN_MAP.items():
					for value in value_list:
						if re.search(re.compile(value), intension) is not None:
							if ( key not in type_set_dict ) or ( next(filter(lambda a: a in type_set_dict[key], root_ancestors), None) is None ):
								pattern_edge_list.append((root,'rdf:type',key))
								if key not in type_set_dict:
									type_set_dict[key] = set()
								type_set_dict[key].add(root)
		return unique_everseen(pattern_edge_list)

	def build(self):
		print('Building knowledge graph..')
		edge_list = self.build_edge_list()

		print('Extracting minimal taxonomy via FCA..')
		hypernym_edge_list = self.extract_minimal_taxonomy(edge_list)
		hypernym_concept_set = get_concept_set(hypernym_edge_list)

		print('Connecting known ontology patterns to concept taxonomy..')
		pattern_hinge_graph = self.connect_taxonomy_to_patterns(hypernym_edge_list)
		# self.print_graph(pattern_hinge_graph, 'kg_hinge')

		print('Creating taxonomy graph..')
		taxonomy_graph = self.format_taxonomy(hypernym_edge_list)
		# self.print_graph(taxonomy_graph, 'kg_taxonomy')
		taxonomy_graph += pattern_hinge_graph
		# self.print_graph(taxonomy_graph, 'kg_hinged_taxonomy')

		return edge_list + taxonomy_graph
