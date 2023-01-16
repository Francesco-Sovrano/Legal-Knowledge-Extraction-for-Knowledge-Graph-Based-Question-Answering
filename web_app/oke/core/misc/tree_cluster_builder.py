import numpy as np
import scipy.cluster.hierarchy as hierarchy
from scipy.spatial import distance
from sklearn.metrics.pairwise import cosine_similarity

def build_hierarchical_cluster(elements, labels, method='centroid', metric='euclidean', optimal_ordering=False):
	cluster = hierarchy.linkage(
		elements, 
		method=method, 
		metric=metric, 
		optimal_ordering=optimal_ordering
	)

	cophentic_correlation_distance, cophenetic_distance_matrix = hierarchy.cophenet(cluster, distance.pdist(elements))
	#print('Cophenetic Distance Matrix', cophenetic_distance_matrix)
	#print('Cophentic Correlation Distance:', cophentic_correlation_distance)

	clusters_dict = {}
	for i, merge in enumerate(cluster):
		# if it is an original point read it from the centers array # other wise read the cluster that has been created
		a = int(merge[0]) if merge[0] <= len(cluster) else clusters_dict[int(merge[0])]
		b = int(merge[1]) if merge[1] <= len(cluster) else clusters_dict[int(merge[1])]
		# the clusters_dict are 1-indexed by scipy
		clusters_dict[1 + i + len(cluster)] = [a,b]
		
	cluster_nested_list = clusters_dict[1 + i + len(cluster)]

	def flatten(container): # iterative flatten, this way we avoid <RecursionError: maximum recursion depth exceeded>
		list_to_flat = [container]
		while len(list_to_flat) > 0:
			current_list_to_flat = list_to_flat.pop()
			for element in current_list_to_flat:
				if isinstance(element, (list,tuple)):
					list_to_flat.append(element)
				else:
					yield element
				
	def build_centroid_tree(nested_list):
		# lazy building, this way we avoid <RecursionError: maximum recursion depth exceeded>
		def let_centroid_tree(nested_list):
			if isinstance(nested_list, (list,tuple)):
				centroid = np.average([elements[e] for e in flatten(nested_list)], 0)
				return {'centroid': centroid, 'sub_tree': (let_centroid_tree(l) for l in nested_list)}
			return {'label': labels[nested_list], 'value': elements[nested_list], 'idx': nested_list}
		centroid_tree = let_centroid_tree(nested_list)
		# eager building
		tree_to_build = [centroid_tree]
		while len(tree_to_build) > 0:
			current_tree_to_build = tree_to_build.pop()
			if 'sub_tree' in current_tree_to_build:
				current_tree_to_build['sub_tree'] = tuple(current_tree_to_build['sub_tree'])
				tree_to_build.extend(current_tree_to_build['sub_tree'])
		return centroid_tree

	return build_centroid_tree(cluster_nested_list), cophentic_correlation_distance

def get_most_similar_leaf(dendrogram, entity_embedding):
	# iterative version to avoid <RecursionError: maximum recursion depth exceeded>
	leaf_list = []
	tree_to_look = [dendrogram]
	while len(tree_to_look) > 0:
		current_tree_to_look = tree_to_look.pop()
		if 'sub_tree' in current_tree_to_look:
			tree_to_look.extend(current_tree_to_look['sub_tree'])
		elif 'value' in current_tree_to_look:
			leaf_list.append(current_tree_to_look)
	if len(leaf_list) == 0:
		return None
	value_list = [
		leaf['value'] 
		for leaf in leaf_list 
		#if leaf['label'] not in centroid_set
	]
	similarity_vec = cosine_similarity([entity_embedding], value_list)
	best_idx = np.argmax(similarity_vec)
	return leaf_list[best_idx]['label']

def build_edge_list(root_dendrogram): # iterative version to avoid <RecursionError: maximum recursion depth exceeded>
	centroid_set = set()
	edge_list = []
	tree_to_build = [(None,root_dendrogram)]
	while len(tree_to_build) > 0:
		parent_label, dendrogram = tree_to_build.pop()
		if 'centroid' in dendrogram:
			centroid_embedding = dendrogram['centroid']
			centroid_label = get_most_similar_leaf(dendrogram, centroid_embedding)
			if centroid_label is not None:
				centroid_set.add(centroid_label)
				if parent_label is not None:
					edge_list.append((parent_label, 'related_to', centroid_label))
				tree_to_build.extend((centroid_label,sub_d) for sub_d in dendrogram['sub_tree'])
		elif 'value' in dendrogram:
			if dendrogram['label'] not in centroid_set: # centroids cannot be leaves
				edge_list.append((parent_label, 'related_to', dendrogram['label']))
	return edge_list
