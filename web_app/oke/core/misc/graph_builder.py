from more_itertools import unique_everseen
from matplotlib import pyplot as plt
import re
import networkx as nx
try:
	import pygraphviz
	from networkx.drawing.nx_agraph import graphviz_layout
except ImportError:
	try:
		import pydotplus
		from networkx.drawing.nx_pydot import graphviz_layout
	except ImportError:
		raise ImportError("This example needs Graphviz and either PyGraphviz or PyDotPlus")

import networkx as nx


def get_betweenness_centrality(edge_list):
	# Betweenness centrality quantifies the number of times a node acts as a bridge along the shortest path between two other nodes.
	di_graph = nx.DiGraph()
	di_graph.add_edges_from(map(lambda x: (x[0],x[-1]), edge_list))
	return nx.betweenness_centrality(di_graph)

def get_concept_description_dict(graph, label_predicate, valid_concept_filter_fn=None):
	if valid_concept_filter_fn:
		concept_set = get_concept_set(filter(valid_concept_filter_fn, graph))
		graph = filter(lambda x: x[0] in concept_set, graph)
	# print('Unique concepts:', len(concept_set))
	uri_dict = {} # concept_description_dict
	for uri,_,label in filter(lambda x: x[1] == label_predicate, graph):
		if uri not in uri_dict:
			uri_dict[uri] = []
		uri_dict[uri].append(label)
	return uri_dict

def get_tuple_element_set(tuple_list, element_idx):
	tuple_element_set = set()
	element_iter = map(lambda x: x[element_idx], tuple_list)
	for element in element_iter:
		if isinstance(element, (list,tuple)):
			for e in element:
				tuple_element_set.add(e)
		else:
			tuple_element_set.add(element)
	return tuple_element_set

def get_subject_set(edge_list):
	return get_tuple_element_set(edge_list, 0)

def get_predicate_set(edge_list):
	return get_tuple_element_set(edge_list, 1)

def get_object_set(edge_list):
	return get_tuple_element_set(edge_list, -1)

def get_concept_set(edge_list):
	edge_list = list(edge_list)
	return get_subject_set(edge_list).union(get_object_set(edge_list))

def get_root_set(edge_list):
	edge_list = list(edge_list)
	return get_subject_set(edge_list).difference(get_object_set(edge_list))

def get_leaf_set(edge_list):
	edge_list = list(edge_list)
	return get_object_set(edge_list).difference(get_subject_set(edge_list))

def reverse_order(edge_list):
	return map(lambda edge: (edge[-1],edge[-2],edge[-3]), edge_list)

def get_ancestors(node, edge_list):
	return get_object_set(filter_graph_by_root_set(list(reverse_order(edge_list)), [node]))

def tuplefy(edge_list):
	def to_tuple(x):
		if type(x) is dict:
			return tuple(x.values())
		if type(x) is list:
			return tuple(x)
		return x
	return [
		tuple(map(to_tuple, edge))
		for edge in edge_list
	]

def build_edge_dict(edge_list, key_fn=lambda x: x):
	edge_dict = {}
	for edge in edge_list:
		for subj in get_subject_set([edge]):
			subj_key = key_fn(subj)
			if subj_key not in edge_dict:
				edge_dict[subj_key] = []
			edge_dict[subj_key].append(edge)
	return edge_dict

def extract_rooted_edge_list(root, edge_dict):
	valid_edge_list = []
	if root not in edge_dict:
		return valid_edge_list
	valid_edge_list += edge_dict[root]
	obj_to_explore = get_object_set(edge_dict[root])
	del edge_dict[root]
	while len(obj_to_explore) > 0:
		obj = obj_to_explore.pop()
		if obj in edge_dict:
			valid_edge_list += edge_dict[obj]
			obj_to_explore |= get_object_set(edge_dict[obj])
			del edge_dict[obj]
	valid_edge_list = list(unique_everseen(valid_edge_list))
	return valid_edge_list

def filter_graph_by_root_set(edge_list, root_set):
	edge_dict = build_edge_dict(edge_list)
	rooted_edge_list_iter = (extract_rooted_edge_list(root, edge_dict) for root in root_set)
	rooted_edge_list = sum(rooted_edge_list_iter, [])
	return rooted_edge_list

def remove_leaves(edge_list, edge_to_remove_fn=lambda x:x):
	edge_list = list(edge_list)
	leaf_to_exclude_set = get_leaf_set(edge_list).intersection(get_object_set(filter(edge_to_remove_fn, edge_list)))
	edge_to_exclude_iter = filter(lambda x: len(get_object_set([x]).intersection(leaf_to_exclude_set))==0, edge_list)
	return list(edge_to_exclude_iter)

def get_connected_graph_list(edge_list):
	edge_list = list(edge_list)
	edge_dict = build_edge_dict(edge_list)
	graph_list = [
		extract_rooted_edge_list(root, edge_dict)
		for root in get_subject_set(edge_list)
	]
	graph_list.sort(key=lambda x: len(x), reverse=True)

	for i,graph in enumerate(graph_list):
		if len(graph)==0:
			continue
		graph_concept_set = get_concept_set(graph)
		for j,other_graph in enumerate(graph_list):
			if i==j:
				continue
			if len(other_graph)==0:
				continue
			other_graph_concept_set = get_concept_set(other_graph)
			if len(graph_concept_set.intersection(other_graph_concept_set)) > 0:
				graph.extend(other_graph)
				graph_concept_set |= other_graph_concept_set
				other_graph.clear()
	graph_list = [
		list(unique_everseen(graph))
		for graph in filter(lambda x: len(x)>0, graph_list)
	]
	return graph_list

def get_biggest_connected_graph(edge_list):
	return max(get_connected_graph_list(edge_list), key=lambda x: len(x))

def save_graphml(edge_list, file_name):
	edge_list = list(edge_list)

	# Build graph
	graph=nx.DiGraph() # directed graph
	for subject, predicate, object in edge_list:
		graph.add_edge(subject, object, r=predicate)
	
	nx.write_graphml(graph, file_name+".graphml", prettyprint=True)
	
	graphml = '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:java="http://www.yworks.com/xml/yfiles-common/1.0/java" xmlns:sys="http://www.yworks.com/xml/yfiles-common/markup/primitives/2.0" xmlns:x="http://www.yworks.com/xml/yfiles-common/markup/2.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:y="http://www.yworks.com/xml/graphml" xmlns:yed="http://www.yworks.com/xml/yed/3" xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://www.yworks.com/xml/schema/graphml/1.1/ygraphml.xsd">
  <!--Created by yEd 3.14.2-->
  <key attr.name="Description" attr.type="string" for="graph" id="d0"/>
  <key for="port" id="d1" yfiles.type="portgraphics"/>
  <key for="port" id="d2" yfiles.type="portgeometry"/>
  <key for="port" id="d3" yfiles.type="portuserdata"/>
  <key attr.name="url" attr.type="string" for="node" id="d4"/>
  <key attr.name="description" attr.type="string" for="node" id="d5"/>
  <key for="node" id="d6" yfiles.type="nodegraphics"/>
  <key for="graphml" id="d7" yfiles.type="resources"/>
  <key attr.name="url" attr.type="string" for="edge" id="d8"/>
  <key attr.name="description" attr.type="string" for="edge" id="d9"/>
  <key for="edge" id="d10" yfiles.type="edgegraphics"/>
  <graph edgedefault="directed" id="G">
	<data key="d0"/>'''

	concept_set = get_concept_set(edge_list)
	for concept in concept_set:
		graphml += '''<node id="{0}">
		<data key="d6">
			<y:ShapeNode>
				<y:Geometry height="44.0" width="162.96822102864604" x="-5597.332280393664" y="-1819.21394393037"/>
				<y:Fill color="#FFFF00" transparent="false"/>
				<y:BorderStyle color="#000000" type="line" width="1.0"/>
				<y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Dialog" fontSize="16" fontStyle="plain" hasBackgroundColor="false" hasLineColor="false" height="23.6015625" modelName="internal" modelPosition="c" textColor="#000000" visible="true" width="131.171875" x="15.89817301432322" y="10.19921875">{0}</y:NodeLabel>
				<y:Shape type="roundrectangle"/>
			</y:ShapeNode>
		</data>
	</node>'''.format(concept) + '\n'
	
	for subj,pred,obj in edge_list:
		graphml += '''<edge source="{0}" target="{1}">
	  <data key="d10">
		<y:PolyLineEdge>
		  <y:Path sx="0.0" sy="0.0" tx="0.0" ty="0.0">
			<y:Point x="-3676.1339400566617" y="-1345.8181620062282"/>
		  </y:Path>
		  <y:LineStyle color="#000000" type="line" width="1.0"/>
		  <y:Arrows source="none" target="standard"/>
		  <y:EdgeLabel alignment="center" backgroundColor="#FFFFFF" distance="2.0" fontFamily="Dialog" fontSize="16" fontStyle="plain" hasLineColor="false" height="23.6015625" modelName="centered" modelPosition="center" preferredPlacement="anywhere" ratio="0.5" textColor="#000000" visible="true" width="100.0390625" x="-101.48474858880354" y="18.27839561095925">{2}<y:PreferredPlacementDescriptor angle="0.0" angleOffsetOnRightSide="0" angleReference="absolute" angleRotationOnRightSide="co" distance="-1.0" frozen="true" placement="anywhere" side="anywhere" sideReference="relative_to_edge_flow"/>
		  </y:EdgeLabel>
		  <y:BendStyle smoothed="false"/>
		</y:PolyLineEdge>
	  </data>
	</edge>'''.format(subj,obj,pred) + '\n'
	
	graphml += '''</graph>
  <data key="d7">
	<y:Resources/>
  </data>
</graphml>'''

	path = file_name+"_yEd.graphml"
	with open(path, 'w') as content_file:
		content_file.write(graphml)

MAX_LABEL_LENGTH = 128
def save_graph(edge_list, file_name, size=None):
	def stringify(x): 
		if isinstance(x, (list,tuple)):
			if len(x)==0:
				return ''
			if len(x)==1:
				x = x[0]
		return str(x)
	edge_list = [tuple(map(stringify,edge)) for edge in edge_list]
	# Build graph
	save_graphml(edge_list, file_name)

	if size is None:
		return
	graph=nx.DiGraph() # directed graph
	format_str = lambda x: x[:MAX_LABEL_LENGTH].replace(':','.')#.replace('.',' ')
	for subject, predicate, object in map(lambda x: map(format_str,x),edge_list):
		graph.add_edge(subject, object, r=predicate)

	#initialze Figure
	plt.figure(num=None, figsize=(size, size))
	plt.axis('off')
	fig = plt.figure(1)

	pos=graphviz_layout(graph,prog='twopi')
	nx.draw(
		graph, 
		pos, 
		font_size=16, 
		with_labels=False,
		arrowstyle='wedge',
	)
	nx.draw_networkx_labels(
		graph, 
		pos, 
		bbox=dict(boxstyle='square', fc="w", ec="k")
	)
	#edge_labels={('A','B'):'AB',('B','C'):'BC',('B','D'):'BD'}
	nx.draw_networkx_edge_labels(
		graph,
		pos,
		edge_labels=nx.get_edge_attributes(graph,'r'),
		font_color='red'
	)

	plt.savefig(file_name+'.png', bbox_inches="tight")
	plt.clf()
	del fig
