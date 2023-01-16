import os
import re
import json
import pandas as pd
from misc.jsonld_lib import *
from misc.doc_reader import get_document_list

def get_dataframe_dict(ontology_dir):
	doc_list = get_document_list(ontology_dir)
	dataframe_dict = {}
	for obj_path in doc_list:
		if obj_path.endswith(('.csv',)):
			print('Parsing:', obj_path)
			_, filename = os.path.split(obj_path)
			class_name = filename.split('.')[0]
			dataframe_dict[class_name] = pd.read_csv(obj_path, sep=';')
	return dataframe_dict

def get_concept_description_dict(ontology_dir):
	dataframe_dict = get_dataframe_dict(ontology_dir)
	
	concept_dict = {}
	for concept, df in dataframe_dict.items():
		concept_dict[concept] = [explode_concept_key(concept).lower().strip()]
		sub_classes = df['SubClasses'].values.tolist()
		concept_dict.update({
			sc: [explode_concept_key(sc).lower().strip()]
			for sc in sub_classes
		})
	return concept_dict

def get_concept_description_dict_from_jsonld(ontology_path, key):
	with open(ontology_path,'r') as f:
		graph = json.load(f)

	return {
		sub_graph['@id']: [explode_concept_key(sub_graph[key]).lower().strip()]
		for sub_graph in graph
		if key in sub_graph
	}

'''
import sys
_, ontology_path, skos_path = sys.argv

print(get_concept_description_dict(ontology_path, skos_path))
'''