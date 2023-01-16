from more_itertools import unique_everseen
import json
import re

class hashabledict(dict):
    def __hash__(self):
        return hash(tuple(sorted(self.items())))

CONCEPT_PREFIX = 'my:'
DOC_PREFIX = 'myfile:'
ANONYMOUS_PREFIX = '_:'
WORDNET_PREFIX = 'wn:'

DOC_ID_PREDICATE = 'my:docID'
HAS_IDX_PREDICATE = 'my:hasIDX'
HAS_SOURCE_PREDICATE = 'my:hasSource'
HAS_LABEL_PREDICATE = 'rdfs:label'
SUBCLASSOF_PREDICATE = 'rdfs:subClassOf'
HAS_TYPE_PREDICATE = 'rdf:type'
CAN_BE_PREDICATE = 'my:canBe'
IN_SYNSET_PREDICATE = 'my:inSynset'
HAS_DEFINITION_PREDICATE = 'dbo:abstract'
CONTENT_PREDICATE = 'my:content'
SPECIAL_PREDICATE_LIST = [
	DOC_ID_PREDICATE,
	HAS_IDX_PREDICATE,
	HAS_SOURCE_PREDICATE,
	HAS_LABEL_PREDICATE,
	SUBCLASSOF_PREDICATE,
	HAS_TYPE_PREDICATE,
	CAN_BE_PREDICATE,
	IN_SYNSET_PREDICATE,
	HAS_DEFINITION_PREDICATE,
	CONTENT_PREDICATE
]

def explode_concept_key(key):
	if not key:
		return ''
	key = re.sub(r"[_-]", " ", key)
	key = key.split(':')[-1]
	if not key:
		return ''
	key = key[0].upper() + key[1:]
	splitted_key = re.findall('[A-Z][^A-Z]*', key)

	# join upper case letters
	i = 0
	j = 1
	while j < len(splitted_key):
		if len(splitted_key[j]) == 1:
			splitted_key[i] += splitted_key[j]
			splitted_key[j] = ''
			j += 1
		else:
			i = j
			j = i+1
	
	exploded_key = ' '.join(splitted_key)
	exploded_key = re.sub(r" +", r" ", exploded_key).strip()
	return exploded_key

def urify(str):
	return str.casefold().strip().replace(' ','_')

def is_html(str):
	html_pattern = r"<(?:\"[^\"]*\"['\"]*|'[^']*'['\"]*|[^'\">])+>"
	return re.match(html_pattern, str, re.IGNORECASE) is not None

def is_url(str):
	if is_rdf_item(str):
		str = str['@value']
	str = str.casefold().strip()
	if not str:
		return False
	if str.startswith('../') or str.startswith('./'):
		return True
	if re.match(r'\w+:', str, re.IGNORECASE) is not None:
		return True
	url_pattern = r'(http[s]?:)?//(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
	return re.match(url_pattern, str, re.IGNORECASE) is not None

def is_rdf_item(v):
	return isinstance(v, dict) and '@value' in v

def is_dict(v):
	return isinstance(v, dict) and '@value' not in v

def is_array(v):
	return isinstance(v, (list,tuple))

def get_jsonld_id(jsonld, default=None):
	if is_dict(jsonld):
		return [jsonld.get('@id',default)]
	if is_array(jsonld):
		return sum(map(lambda x: get_jsonld_id(x,default),jsonld),[])
	if is_rdf_item(jsonld):
		return [jsonld['@value']]
	return [jsonld]

def get_string_from_triple(triple): 
	def format_element(element,predicate):
		if is_rdf_item(element):
			element = element['@value']
		if not is_array(element):
			element = [element]
		element = filter(lambda x: not isinstance(x, str) or not x.startswith(CONCEPT_PREFIX), element)
		element = map(lambda x: explode_concept_key(' '.join(x[3:].split('.')[:-2]) if x.startswith(WORDNET_PREFIX) else x) if isinstance(x, str) else x, element)
		element = filter(lambda x: x, unique_everseen(element))
		element = list(element)
		filtered_element = (
			a.strip('.')
			for a in element	
			if next(filter(lambda x: a in x and a != x, element), None) is None
		)
		if predicate in [DOC_ID_PREDICATE,HAS_IDX_PREDICATE,HAS_SOURCE_PREDICATE,HAS_LABEL_PREDICATE]:
			filtered_element = map(lambda x: f'«{x}»', filtered_element)
		filtered_element = sorted(filtered_element, key=lambda x:len(x))
		if len(filtered_element) == 0:
			return ''
		formatted_triple = filtered_element[0]
		if len(filtered_element) > 1:
			formatted_triple += f' (or: {", ".join(filtered_element[1:])})'
		return formatted_triple
	subj,pred,obj = triple
	subj = format_element(subj,pred)#.lower().strip()
	obj = format_element(obj,pred)#.lower().strip()
	if subj == '' or obj == '':
		return ''
	# Get special predicates templates
	if pred == DOC_ID_PREDICATE:
		pred = '{subj} has been found in document {obj}'
	elif pred == HAS_IDX_PREDICATE:
		pred = '{subj} starts at offset {obj} of its document'
	elif pred == HAS_SOURCE_PREDICATE:
		pred = '{subj} is in the sentence {obj}'
	elif pred == HAS_LABEL_PREDICATE:
		pred = '{subj} is called {obj}'
	elif pred == SUBCLASSOF_PREDICATE:
		pred = '{subj} is {obj}'
	elif pred == HAS_TYPE_PREDICATE:
		pred = '{subj} is {obj}'
	elif pred == CAN_BE_PREDICATE:
		pred = '{subj} can be {obj}'
	elif pred == IN_SYNSET_PREDICATE:
		pred = '{subj} is the same of {obj}'
	elif pred == HAS_DEFINITION_PREDICATE:
		pred = '{subj} is: {obj}'
	# Converts a rdf triple into a string, by executing the predicate template on subject and object.
	triple_str = pred#.lower().strip()
	triple_str = triple_str.replace('{subj}',subj) if '{subj}' in triple_str else ' '.join([subj,triple_str])
	triple_str = triple_str.replace('{obj}',obj) if '{obj}' in triple_str else ' '.join([triple_str,obj])
	triple_str = triple_str.replace('(be)','is')
	triple_str = re.sub(r' +([,;.])',r'\1',triple_str) # remove unneeded whitespaces
	triple_str = re.sub(r' +/ +',r'/',triple_str) # remove unneeded whitespaces
	triple_str = triple_str.replace(' )',')').replace('( ','(') # remove unneeded whitespaces
	triple_str = re.sub(r'^: ','',triple_str).replace(' : ',': ').replace('::',':').replace('.,',';')
	return triple_str#.replace(',','')

def jsonld_to_triples(jsonld, base_id=None):
	def helper(j, default_subj_id=None, uid=0):
		triples = []
		if not default_subj_id:
			default_subj_id = f'{ANONYMOUS_PREFIX}{base_id}_{uid}'
		if is_array(j):
			for x in j:
				new_triples, uid = helper(x, default_subj_id, uid)
				triples += new_triples
		elif is_dict(j):
			subj_id = get_jsonld_id(j, default_subj_id)[0]
			if not subj_id:
				raise ValueError('A subject is required.')
			# subj_id = subj_id.lower().strip()
			for pred,obj in j.items():
				if pred == '@id':
					continue
				# pred = pred.casefold().strip()
				# if is_rdf_item(obj):
				# 	triples.append((subj_id,pred,hashabledict(obj)))
				# 	continue
				for obj_id in get_jsonld_id(obj):
					if not obj_id: # new uid, increase the old one
						uid += 1
						obj_id = f'{ANONYMOUS_PREFIX}{base_id}_{uid}'
					# if is_url(obj_id):
					# 	obj_id = obj_id.lower().strip()
					triples.append((
						subj_id, 
						pred, 
						obj_id,
					))
					new_triples, uid = helper(obj, obj_id, uid)
					triples += new_triples
		return triples, uid
	return helper(jsonld)[0]
