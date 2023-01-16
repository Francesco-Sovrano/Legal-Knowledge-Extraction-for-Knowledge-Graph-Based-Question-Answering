import os
import pickle
import re
import json
from bs4 import BeautifulSoup
from tika import parser
import unicodedata
from more_itertools import unique_everseen
from misc.jsonld_lib import *
import html

get_bs_text = lambda x: re.sub(r'[ \n\t]+',' ',html.unescape(x.text)).strip() if x else None

def normalize_string(content):
	content = unicodedata.normalize("NFKC", content) # normalize content
	content = re.sub(r'\r\n', '\n', content, flags=re.UNICODE) # normalize new lines
	content = re.sub(r'[\r\f\v]', '\n', content, flags=re.UNICODE) # normalize new lines
	content = re.sub(r'[-\x2D\xAD\x58A\x1806\xFE63\xFF0D\xE002D]\n+', '', content, flags=re.UNICODE) # remove word-breaks (hyphens)
	content = re.sub(r'[\x2010\x2011\x2027\x2043]\n+', ' ', content, flags=re.UNICODE) # remove line-breaks (hyphens)
	content = re.sub(r'([^\n.])\n+([^\n])', r'\1 \2', content, flags=re.UNICODE) # remove line-breaks
	content = re.sub(r'[ \t]+', ' ', content, flags=re.UNICODE) # normalize whitespaces
	# workarounds
	content = re.sub(r' - ', ' ', content, flags=re.UNICODE) # remove all hyphens
	content = re.sub(r'- *', '', content, flags=re.UNICODE) # remove all hyphens
	return content.strip()

def get_document_list(directory):
	doc_list = []
	for obj in os.listdir(directory):
		obj_path = os.path.join(directory, obj)
		if os.path.isfile(obj_path):
			doc_list.append(obj_path)
		elif os.path.isdir(obj_path):
			doc_list.extend(get_document_list(obj_path))
	return doc_list

def get_all_paths_to_leaf(root, element_set):
	if not root:
		return [[]]
	if root.name in element_set:
		return [[root]]
	children = list(root.findChildren(recursive=False))
	if not children:
		return [[]]
	path_list = [
		path
		for child in children
		for path in get_all_paths_to_leaf(child, element_set)
	]
	merged_path_list = []
	i = 0
	while i < len(path_list):
		child_path = []
		while i < len(path_list) and len(path_list[i]) == 1:
			child_path += path_list[i]
			i+=1
		if i < len(path_list):
			child_path += path_list[i]
			i+=1
		if child_path:
			merged_path_list.append(child_path)
	return merged_path_list

def get_next_siblings(e, name_set):
	next_siblings = []
	sibling = e.find_next_sibling()
	while sibling and sibling.name in name_set:
		next_siblings.append(sibling)
		sibling = sibling.find_next_sibling()
	return next_siblings

def read_jsonld_file(filename):
	file_id = os.path.basename(filename).replace(' ','_')
	# read file
	with open(f'{filename}.json', 'r') as f:
		data=f.read()
	# parse file
	obj = json.loads(data)
	triple_list = jsonld_to_triples(obj, file_id)
	# print(json.dumps(triple_list, indent=4))
	annotated_text_list = [
		{
			'text': o if not is_rdf_item(o) else o['@value'],
			'id': file_id,
		}
		for s,p,o in triple_list
		if not is_url(o) and p != HAS_LABEL_PREDICATE
	] + [{
		'graph': triple_list
	}]
	return annotated_text_list

def read_html_file(filename, short_extension=False):
	file_id = os.path.basename(filename).replace(' ','_')
	with open(filename+('.htm' if short_extension else '.html'), 'r', encoding='utf8', errors='ignore') as file:
		file_content = file.read()
	doc = BeautifulSoup(file_content, features="lxml")
	for script in doc(["script", "style"]): # remove all javascript and stylesheet code
		script.extract()
	annotated_text_list = []
	p_to_ignore = set()
	elements_to_merge = set(['table','ul','ol'])
	for i,p in enumerate(doc.findAll("p")):
		p_text = get_bs_text(p)
		if p_text in p_to_ignore:
			continue
		p_to_ignore.add(p_text)
		# p_set = [p] + get_next_siblings(p,['p'])
		# p_to_ignore |= set(p_set)
		# p = p_set[-1]
		siblings_to_merge = get_next_siblings(p,elements_to_merge)
		if not siblings_to_merge:
			annotated_text_list.append({
				'text': p_text,
				# 'text': ' '.join(map(get_bs_text,p_set)),
				'id': file_id,
			})
		else:
			for sibling in siblings_to_merge:
				path_list = get_all_paths_to_leaf(sibling, ['p'])
				annotated_text_list += [
					{
						'text': ' '.join(map(get_bs_text, [p]+path)),
						'id': file_id,
					}
					for path in path_list
				]
				p_to_ignore |= set(map(get_bs_text, sum(path_list,[])))
	# print(json.dumps(annotated_text_list, indent=4))
	return list(unique_everseen(annotated_text_list, key=lambda x: x['text']))

def read_pdf_file(filename): # https://unicodelookup.com
	file_id = os.path.basename(filename).replace(' ','_')
	raw = parser.from_file(filename+'.pdf')
	return [
		{
			'text': paragraph.strip(),
			'id': file_id
		}
		for paragraph in raw['content'].split('\n\n')
		if paragraph
	]

def read_akn_file(filename):
	file_id = os.path.basename(filename).replace(' ','_')
	doc_id = urify(os.path.basename(filename))
	def get_num_jsonld(e):
		num = get_bs_text(e.num)
		if not num:
			return None
		return {
			'@id': doc_id+':'+e['eid'],
			HAS_LABEL_PREDICATE: num
		}
	def get_heading_jsonld(e):
		heading = get_bs_text(e.heading)
		jsonld = get_num_jsonld(e)
		if heading:
			if jsonld:
				jsonld['my:heading'] = heading
			else:
				return {
					'@id': doc_id+':'+e['eid'],
					'my:heading': heading
				}
		return jsonld
	
	with open(filename+'.akn') as f: 
		file_content = f.read()

	doc = BeautifulSoup(file_content, features="lxml")

	annotated_text_list = []
	for i,p in enumerate(doc.findAll("p")):
		text = get_bs_text(p)
		# Get annotations
		text_annotation = {}
		# # Get parent list
		# parent_list = [{
		# 	'name': p.name,
		# 	'attrs': p.attrs
		# }]
		# for parent in p.find_parents():
		# 	if parent.name == 'akomantoso': # Ignore the remaining parents
		# 		break
		# 	parent_list.append({
		# 		'name': parent.name,
		# 		'attrs': parent.attrs
		# 	})
		# text_annotation['@id'] = doc_id+':'+json.dumps(parent_list)
		# Get block
		block_list = p.find_parent('blocklist')
		if block_list:
			list_introduction = block_list.find('listintroduction')
			if list_introduction:
				text = ' '.join((get_bs_text(list_introduction), text))
			item = p.find_parent('item')
			item_num = get_num_jsonld(item)
			if item_num:
				text_annotation['my:block_id'] = item_num
		else:
			intro = p.find_parent('intro') 
			if intro:
				continue
			list = p.find_parent('list')
			if list and list.intro:
				text = ' '.join((get_bs_text(list.intro.p), text))
		# Get paragraph
		paragraph = p.find_parent('paragraph')
		if paragraph:
			paragraph_num = get_num_jsonld(paragraph)
			if paragraph_num:
				text_annotation['my:paragraph_id'] = paragraph_num
		# Get article
		article = p.find_parent('article')
		if article:
			article_num = get_num_jsonld(article)
			if article_num:
				text_annotation['my:article_id'] = article_num
		# Get section
		section = p.find_parent('section')
		if section:
			section_heading = get_heading_jsonld(section)
			if section_heading:
				text_annotation['my:section_id'] = section_heading
		# Get chapter
		chapter = p.find_parent('chapter')
		if chapter:
			chapter_heading = get_heading_jsonld(chapter)
			if chapter_heading:
				text_annotation['my:chapter_id'] = chapter_heading
		# Get references
		text_annotation['my:reference_id'] = [
			{
				'@id': doc_id+':'+ref['href'],
				HAS_LABEL_PREDICATE: get_bs_text(ref), 
			}
			for ref in p.findAll('ref', recursive=False)
		]
		base_id = f'{file_id}_{i}'
		annotated_text_list.append({
			'text': text,
			'id': file_id,
			'annotation': {
				'root': f'{ANONYMOUS_PREFIX}{base_id}_0',
				'content': jsonld_to_triples(text_annotation, base_id),
			},
		})
	return annotated_text_list

def get_content_list(doc_list):
	file_name = lambda x: os.path.splitext(x)[0]
	doc_set = set(doc_list)
	name_iter = unique_everseen(map(file_name, doc_list))
	content_list = []
	for obj_name in name_iter:
		if obj_name+'.akn' in doc_set:
			print('Parsing AKN:', obj_name)
			content_list += read_akn_file(obj_name)
		elif obj_name+'.html' in doc_set:
			print('Parsing HTML:', obj_name)
			content_list += read_html_file(obj_name)
		elif obj_name+'.htm' in doc_set:
			print('Parsing HTM:', obj_name)
			content_list += read_html_file(obj_name, True)
		elif obj_name+'.pdf' in doc_set:
			print('Parsing PDF:', obj_name)
			content_list += read_pdf_file(obj_name)
		elif obj_name+'.json' in doc_set:
			print('Parsing JSON-LD:', obj_name)
			content_list += read_jsonld_file(obj_name)
	return content_list

def create_cache(file_name, create_fn):
	print(f'Creating cache <{file_name}>..')
	result = create_fn()
	with open(file_name, 'wb') as f:
		pickle.dump(result, f)
	return result

def load_cache(file_name):
	if os.path.isfile(file_name):
		print(f'Loading cache <{file_name}>..')
		with open(file_name,'rb') as f:
			return pickle.load(f)
	return None

def load_or_create_cache(file_name, create_fn):
	result = load_cache(file_name)
	if not result:
		result = create_cache(file_name, create_fn)
	return result

class DocParser():

	# def __init__(self, model_options):
	# 	super().__init__(model_options)

	def set_documents_path(self, doc_path):
		self.content_list = get_content_list(get_document_list(doc_path))
		self.process_content_list()
		return self

	def set_document_list(self, doc_list):
		self.content_list = get_content_list(doc_list)
		self.process_content_list()
		return self

	def set_content_list(self, content_list):
		self.content_list = tuple(map(lambda x: x if isinstance(x,dict) else {'text':x,'id':x}, content_list))
		self.process_content_list()
		return self

	def process_content_list(self):
		self.graph_list = tuple(filter(lambda x: x, map(lambda x: x.get('graph', None), self.content_list)))
		self.content_list = tuple(filter(lambda x: 'text' in x, self.content_list))
		for doc_dict in self.content_list:
			doc_dict['normalised_text'] = normalize_string(doc_dict['text'])

	def get_doc_iter(self):
		for doc_dict in self.content_list:
			yield doc_dict['id']

	def get_annotation_iter(self):
		for doc_dict in self.content_list:
			yield doc_dict.get('annotation',None)

	def get_graph_iter(self):
		return self.graph_list

	def get_content_iter(self, normalised=True):
		for doc_dict in self.content_list:
			yield doc_dict['normalised_text' if normalised else 'text']
