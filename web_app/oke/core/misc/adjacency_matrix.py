import json

class AdjacencyMatrix():
	
	def __init__(self, graph, equivalence_relation_set, is_sorted=False): # Build the adjacency matrix, for both incoming and outcoming edges
		self.graph = graph
		self.equivalence_matrix = {}
		self.adjacency_matrix = {}
		for s,p,o in graph:
			if o not in self.adjacency_matrix:
				self.adjacency_matrix[o] = {'in': [], 'out': []}
			if s not in self.adjacency_matrix:
				self.adjacency_matrix[s] = {'in': [], 'out': []}
			if p not in equivalence_relation_set:
				continue
			if s not in self.equivalence_matrix:
				self.equivalence_matrix[s] = set()
			if o not in self.equivalence_matrix:
				self.equivalence_matrix[o] = set()
			self.equivalence_matrix[s].add(o)
			for e in self.equivalence_matrix[s]:
				if e == o:
					continue
				self.equivalence_matrix[e].add(o)
			self.equivalence_matrix[o].add(s)
			for e in self.equivalence_matrix[o]:
				if e == s:
					continue
				self.equivalence_matrix[e].add(s)
		# print(json.dumps(dict(map(lambda x:(x[0],list(x[1])), self.equivalence_matrix.items())), indent=4))
		for s,p,o in graph:
			self.adjacency_matrix[s]['out'].append((p,o))
			for e in self.equivalence_matrix.get(s,[]):
				self.adjacency_matrix[e]['out'].append((p,o))
			self.adjacency_matrix[o]['in'].append((p,s))
			for e in self.equivalence_matrix.get(o,[]):
				self.adjacency_matrix[e]['in'].append((p,s))
		# print(json.dumps(self.adjacency_matrix['my:cem'], indent=4))
		if is_sorted:
			for concept in self.adjacency_matrix.values():
				concept['in'].sort()
				concept['out'].sort()

	def get_incoming_edges_matrix(self, concept):
		adjacency_list = self.adjacency_matrix.get(concept,None)
		return list(adjacency_list['in']) if adjacency_list else []

	def get_outcoming_edges_matrix(self, concept):
		adjacency_list = self.adjacency_matrix.get(concept,None)
		return list(adjacency_list['out']) if adjacency_list else []

	def get_equivalent_concepts(self, concept):
		return set(self.equivalence_matrix.get(concept,[]))

	def get_nodes(self):
		return self.adjacency_matrix.keys()

	def get_predicate_chain(self, concept_set, direction_set, predicate_filter_fn=None, depth=None, already_explored_concepts_set=None): # This function returns the related concepts of a given concept set for a given type of relations (e.g. if the relation is rdfs:subclassof, then it returns the super- and/or sub-classes), exploting an adjacency matrix
		if depth:
			depth -= 1
		if not already_explored_concepts_set:
			already_explored_concepts_set = set()
		joint_set = set()
		already_explored_concepts_set |= concept_set
		for c in concept_set:
			for direction in direction_set:
				adjacency_list = self.adjacency_matrix.get(c,None)
				if adjacency_list:
					adjacency_iter = filter(lambda x: x[-1] not in already_explored_concepts_set, adjacency_list[direction])
					if predicate_filter_fn:
						adjacency_iter = filter(lambda x: predicate_filter_fn(x[0]), adjacency_iter)
					joint_set |= set(map(lambda y: y[-1], adjacency_iter))
		if len(joint_set) == 0:
			return set(concept_set)
		elif depth and depth <= 0:
			return joint_set.union(concept_set)
		return concept_set.union(self.get_predicate_chain(
			joint_set, 
			direction_set,
			predicate_filter_fn=predicate_filter_fn, 
			depth=depth, 
			already_explored_concepts_set=already_explored_concepts_set,
		))

	# Tarjan's algorithm (single DFS) for finding strongly connected components in a given directed graph
	def SCC(self): # Complexity : O(V+E) 
		'''A recursive function that finds and prints strongly connected 
		components using DFS traversal 
		u --> The vertex to be visited next 
		disc[] --> Stores discovery times of visited vertices 
		low[] -- >> earliest visited vertex (the vertex with minimum 
					discovery time) that can be reached from subtree 
					rooted with current vertex 
		 st -- >> To store all the connected ancestors (could be part 
			   of SCC) 
		 stackMember[] --> bit/index array for faster check whether 
					  a node is in stack 
		'''
		def helper(clique_list, u, low, disc, stackMember, st, Time=0): 
			# Initialize discovery time and low value 
			disc[u] = Time 
			low[u] = Time 
			Time += 1
			stackMember[u] = True
			st.append(u) 

			# Go through all vertices adjacent to this 
			for _,v in self.adjacency_matrix[u]['in']: 
				  
				# If v is not visited yet, then recur for it 
				if disc[v] == -1: 
					Time = helper(clique_list, v, low, disc, stackMember, st, Time) 

					# Check if the subtree rooted with v has a connection to 
					# one of the ancestors of u 
					# Case 1 (per above discussion on Disc and Low value) 
					low[u] = min(low[u], low[v]) 
							  
				elif stackMember[v] == True:  

					'''Update low value of 'u' only if 'v' is still in stack 
					(i.e. it's a back edge, not cross edge). 
					Case 2 (per above discussion on Disc and Low value) '''
					low[u] = min(low[u], disc[v]) 

			# head node found, pop the stack and print an SCC 
			w = -1 #To store stack extracted vertices 
			if low[u] == disc[u]:
				clique = [] 
				while w != u: 
					w = st.pop() 
					clique.append(w)
					stackMember[w] = False
				clique_list.append(clique)
			return Time  
		# Mark all the vertices as not visited  
		# and Initialize parent and visited,  
		# and ap(articulation point) arrays 
		disc = {k:-1 for k in self.adjacency_matrix.keys()}
		low = {k:-1 for k in self.adjacency_matrix.keys()}
		stackMember = {k:False for k in self.adjacency_matrix.keys()}
		st =[] 
		  

		# Call the recursive helper function  
		# to find articulation points 
		# in DFS tree rooted with vertex 'i' 
		clique_list = []
		Time = 0
		for i in self.adjacency_matrix.keys(): 
			if disc[i] == -1: 
				Time = helper(clique_list, i, low, disc, stackMember, st, Time)
		return clique_list
