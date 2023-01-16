from misc.doc_reader import DocParser
from models.model_manager import ModelManager
from collections import Counter
import re
from more_itertools import unique_everseen

### https://spacy.io/api/annotation
# 'acl',		# clausal modifier of noun (adjectival clause)
# 'acomp',		# adjectival complement
# 'advcl',		# adverbial clause modifier
# 'advmod',		# adverbial modifier
# 'agent',		# agent
# 'amod',		# adjectival modifier
# 'appos',		# appositional modifier
# 'attr',		# attribute
# 'aux',		# auxiliary
# 'auxpass',	# auxiliary (passive)
# 'case',		# case marking
# 'cc',			# coordinating conjunction
# 'ccomp',		# clausal complement
# 'compound',	# compound
# 'conj',		# conjunct
# 'cop',		# copula
# 'csubj',		# clausal subject
# 'csubjpass',	# clausal subject (passive)
# 'dative',		# dative
# 'dep',		# unclassified dependent
# 'det',		# determiner
# 'dobj',		# direct object
# 'expl',		# expletive
# 'intj',		# interjection
# 'mark',		# marker
# 'meta',		# meta modifier
# 'neg',		# negation modifier
# 'nn',			# noun compound modifier
# 'nounmod',	# modifier of nominal
# 'npmod',		# noun phrase as adverbial modifier
# 'nsubj',		# nominal subject
# 'nsubjpass',	# nominal subject (passive)
# 'nummod',		# numeric modifier
# 'oprd',		# object predicate
# 'obj',		# object
# 'obl',		# oblique nominal
# 'parataxis',	# parataxis
# 'pcomp',		# complement of preposition
# 'pobj',		# object of preposition
# 'poss',		# possession modifier
# 'preconj',	# pre-correlative conjunction
# 'prep',		# prepositional modifier
# 'prt',		# particle
# 'punct',		# punctuation
# 'quantmod',	# modifier of quantifier
# 'relcl',		# relative clause modifier
# 'root',		# root
# 'xcomp',		# open clausal complement

class ConceptExtractor(ModelManager):

	SUBJ_IDENTIFIER = [ # dependency markers for subjects
		'subj',
		'expl',		# expletive
	]
	OBJ_IDENTIFIER = [ # dependency markers for objects
		'obj',
		'obl',		# oblique nominal
		'intj',		# interjection
		'attr',		# attribute - http://www.english-for-students.com/an-attribute-1.html
		'oprd',		# object predicate
		# # Verbal objects
		'acomp',	# adjectival complement
		'xcomp',	# open clausal complement
	]
	CONCEPT_IDENTIFIER = SUBJ_IDENTIFIER + OBJ_IDENTIFIER
	AMOD_IDENTIFIER = [
		'amod',		#adjectival modifier
	]
	EXTENDED_CHUNK_IDENTIFIER = [ # https://universaldependencies.org/u/dep/all.html
		'det',		# determiner
		'punct',	# punctuation
		# Multiword Expression
		'fixed', 'flat', 'compound',	# compound
		'subtok', 	# eg. the 'non' and the '-' in 'non-contractual obligations'
		'case',		# case marking
		'dep',		# unclassified dependent
		# Normal Modifiers
		'mod',
		'nn',		# noun compound modifier
		'meta',		# meta modifier
		'neg',		# negation modifier
		'poss',		# possession modifier
		'appos',	# appositional modifier
	]
	PREP_IDENTIFIER = [
		'prep',		# prepositional modifier
	]
	# CLAUSE_IDENTIFIER = [
	# 	# Clausal Modifiers (noun + verb)
	# 	'acl',		# clausal modifier of noun (adjectival clause)
	# 	'relcl',	# relative clause modifier
	# 	'advcl',	# adverbial clause modifier
	# 	# Verbal objects
	# 	'mark', 	# marker - https://universaldependencies.org/docs/en/dep/mark.html
	# 	'prt',		# particle
	# 	'agent',	# agent
	# 	'dative',	# dative
	# 	'advmod',	# adverbial modifier
	# 	'aux',		# auxiliaries
	# 	# Complements
	# 	# 'acomp',	# adjectival complement
	# 	# 'xcomp',	# open clausal complement
	# 	# 'pcomp',	# complement of preposition
	# 	# 'ccomp',	# clausal complement
	# ]
	SUBJ_REGEXP = re.compile('|'.join(SUBJ_IDENTIFIER))
	OBJ_REGEXP = re.compile('|'.join(OBJ_IDENTIFIER))
	CONCEPT_REGEXP = re.compile('|'.join(CONCEPT_IDENTIFIER))
	AMOD_REGEXP = re.compile('|'.join(AMOD_IDENTIFIER))
	EXTENDED_CHUNK_REGEXP = re.compile('|'.join(EXTENDED_CHUNK_IDENTIFIER))
	GROUP_REGEXP = re.compile('|'.join(CONCEPT_IDENTIFIER+PREP_IDENTIFIER+EXTENDED_CHUNK_IDENTIFIER))
	# CLAUSE_REGEXP = re.compile('|'.join(CONCEPT_IDENTIFIER+PREP_IDENTIFIER+EXTENDED_CHUNK_IDENTIFIER+CLAUSE_IDENTIFIER))
	
	def __init__(self, model_options):
		super().__init__(model_options)
		self.min_sentence_token_count = model_options.get('min_sentence_token_count',3)
		self.min_sentence_whitespace_count = self.min_sentence_token_count-1
		self.disable_spacy_component = ["ner","textcat"]

	@staticmethod
	def get_referenced_span(token):
		# if token.pos_ == 'PRON' and token._.in_coref:
		# 	#for cluster in token._.coref_clusters:
		# 	#	print(token.text + " => " + cluster.main.text)
		# 	return ConceptExtractor.trim_prepositions(list(token._.coref_clusters[0].main))
		return [token]

	@staticmethod
	def get_token_lemma(token, prevent_verb_lemmatization=False):
		return token.lemma_ if not prevent_verb_lemmatization or token.pos_!='VERB' else token.text

	@staticmethod
	def get_span_lemma(span, prevent_verb_lemmatization=False, hidden_dep_list=[]):
		forbidden_pos = set(('DET','PUNCT','CCONJ'))
		expanded_span = sum((ConceptExtractor.get_referenced_span(e) for e in span),[])
		return ' '.join((
			ConceptExtractor.get_token_lemma(e, prevent_verb_lemmatization=prevent_verb_lemmatization)
			for e in expanded_span 
			if e.lemma_ != '-PRON-' # no pronouns in lemma
			and e.pos_ not in forbidden_pos # no determiners, punctuation, conjunctions
			and ConceptExtractor.get_token_dependency(e) not in hidden_dep_list
		)).strip()#.replace(' - ','') # replace subtokens

	@staticmethod
	def get_concept_text(concept):
		return ' '.join(
			' '.join(
				t.text 
				for t in ConceptExtractor.get_referenced_span(c)
			).strip() 
			for c in concept
		).strip().replace(' - ','') # replace subtokens

	@staticmethod
	def trim(token_list, trim_fn):
		while len(token_list) > 0 and trim_fn(token_list[-1]):
			del token_list[-1]
		while len(token_list) > 0 and trim_fn(token_list[0]):
			del token_list[0]
		return token_list

	@staticmethod
	def trim_prepositions(token_list):
		# punct_to_remove = set([',','.',';','"',"'"])
		return ConceptExtractor.trim(token_list, lambda x: ConceptExtractor.get_token_dependency(x) in ['prep','punct'])

	@staticmethod
	def get_token_dependency(token):
		if token.dep_ != 'conj':
			return token.dep_
		for t in token.ancestors:
			if t.dep_ != 'conj':
				return t.dep_

	@staticmethod
	def get_token_ancestors(token):
		conjunction_count = 1 if token.dep_ == 'conj' else 0
		for ancestor in token.ancestors:
			if ancestor.dep_ == 'conj':
				conjunction_count += 1
				if conjunction_count == 1:
					yield ancestor
				else:
					continue
			elif conjunction_count > 0:
				conjunction_count = 0
				continue
			yield ancestor

	@staticmethod
	def get_token_descendants(token, filter_fn=lambda x:x):
		for c in filter(filter_fn, token.children):
			yield c
			for o in ConceptExtractor.get_token_descendants(c, filter_fn):
				yield o

	@staticmethod
	def get_consecutive_tokens(core_concept, concept_span):
		core_concept_index_in_span = core_concept.i
		return [
			t
			for i,t in enumerate(concept_span)
			if abs(t.i-core_concept_index_in_span) == i
		]

	@staticmethod
	def get_composite_concept(core_concept, dep_regexp=None, fellow_filter_fn=lambda x: x.dep_ != 'conj'):
		if dep_regexp:
			filter_fn = lambda x: fellow_filter_fn(x) and re.search(dep_regexp, ConceptExtractor.get_token_dependency(x))
		else:
			filter_fn = fellow_filter_fn
		concept_span = [core_concept]
		concept_span += ConceptExtractor.get_token_descendants(core_concept, filter_fn)
		concept_span = sorted(
			unique_everseen(
				concept_span, 
				key=lambda x: x.idx
			), 
			key=lambda x: x.idx
		)
		# concept_span = ConceptExtractor.get_consecutive_tokens(core_concept, concept_span)
		# concept_span = ConceptExtractor.trim_prepositions(concept_span)
		return tuple(concept_span)

	@staticmethod
	def get_concept_dict_from_span(span, prevent_verb_lemmatization=False, hidden_dep_list=[]):
		# print(list(map(lambda x: (x.text, x.pos_, x.dep_), span)))
		return {
			'span': tuple(span),
			'text': ConceptExtractor.get_concept_text(span).lower(),
			'lemma': ConceptExtractor.get_span_lemma(span, prevent_verb_lemmatization, hidden_dep_list).lower(),
			'idx': tuple((s.idx,s.idx+len(s)) for s in span)
		}

	@staticmethod
	def get_concept_dict_uid(concept_dict):
		return (concept_dict['text'], concept_dict['idx'])

	@staticmethod
	def get_source_dict_uid(source_dict):
		return (source_dict['sentence_text'], source_dict['doc'])

	@staticmethod
	def get_concept_dict_size(concept_dict):
		return (len(concept_dict['span']),len(concept_dict['text']))

	@staticmethod
	def get_related_concept_iter(token):
		# Get composite concepts
		core_concept = (token,)
		if not core_concept:
			return []
		concept_chunk = tuple(next(filter(lambda nc: token in nc, token.sent.noun_chunks), core_concept))
		concept_dict_list = sorted(
			map(
				ConceptExtractor.get_concept_dict_from_span, 
				unique_everseen(
					map(
						lambda x: tuple(ConceptExtractor.trim_prepositions(list(x))),
						(
							core_concept, 
							ConceptExtractor.get_composite_concept(token, ConceptExtractor.AMOD_REGEXP), 
							concept_chunk, 
							ConceptExtractor.get_composite_concept(token, ConceptExtractor.EXTENDED_CHUNK_REGEXP), 
							ConceptExtractor.get_composite_concept(token, ConceptExtractor.GROUP_REGEXP),
							ConceptExtractor.get_composite_concept(token, None, lambda x: x), # get the whole subtree
						)
					),
					key=lambda x: tuple(map(lambda y: y.idx, x))
				)
			),
			key=ConceptExtractor.get_concept_dict_size # tokens' length + whitespaces
		)
		# Build concept iter
		related_concept_iter = [
			{
				'source': { # Get sentece
					'sentence_text': token.sent.text,
					'paragraph_text': token.doc.text,
					# 'sent_idx': token.sent[0].idx, # the position of the sentence inside the documents
				},
				'concept': concept_dict, 
				'concept_core': tuple(reversed(concept_dict_list[:i]) if i > 1 else concept_dict_list[:1])
			}
			for i,concept_dict in enumerate(concept_dict_list)
		]
		return related_concept_iter

	@staticmethod
	def is_core_concept(token):
		dep = ConceptExtractor.get_token_dependency(token)
		return re.search(ConceptExtractor.CONCEPT_REGEXP, dep) or (dep =='ROOT' and token.pos_=='NOUN')

	def get_concept_list(self, doc_parser: DocParser):
		def get_concept_list_by_doc(doc_id, processed_doc, annotation_dict):
			core_concept_list = [
				token
				for token in processed_doc
				if self.is_core_concept(token)
			]
			# print(core_concept_list)
			# print([
			# 	(token.text,ConceptExtractor.get_token_dependency(token), token.dep_, token.pos_, list(token.ancestors)) 
			# 	for token in processed_doc
			# ])

			concept_list = []
			for t in core_concept_list:
				concept_list += list(self.get_related_concept_iter(t))
				
			concept_iter = iter(concept_list)
			concept_iter = unique_everseen(concept_iter, key=lambda c: self.get_concept_dict_uid(c['concept']))
			concept_list = list(concept_iter)
			for concept_dict in concept_list:
				concept_dict['source']['doc'] = doc_id
				concept_dict['source']['annotation'] = annotation_dict
			return concept_list
		doc_iter = doc_parser.get_doc_iter()
		annotation_iter = doc_parser.get_annotation_iter()
		spacy_doc_iter = self.nlp(tuple(doc_parser.get_content_iter()))
		return sum(map(lambda x: get_concept_list_by_doc(*x), zip(doc_iter, spacy_doc_iter, annotation_iter)), [])

	@staticmethod
	def find_path_to_closest_in_set(core, core_set):
		path = set()
		if core in core_set:
			return (path,core)
		for ancestor in ConceptExtractor.get_token_ancestors(core):
			if ancestor in core_set:
				return (path,ancestor)
			path.add(ancestor)
		return (path,None)

	@staticmethod
	def get_concept_counter_dict(concept_list):
		return {
			concept: {'count': count}
			for concept, count in Counter(concept_list).items()
		}
