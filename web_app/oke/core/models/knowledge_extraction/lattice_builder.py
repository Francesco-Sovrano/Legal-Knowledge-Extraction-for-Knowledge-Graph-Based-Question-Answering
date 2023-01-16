from more_itertools import unique_everseen
from concepts import Context

class LatticeBuilder():
	def __init__(self, templatize=True):
		self.formal_concept_context_list = []
		self.templatize = templatize

	@staticmethod
	def deanonymize_graph(edge_list, name_fn=lambda c:c, key_fn=lambda c:c):
		def build_edge_dict(edge_list, key_fn=lambda x: x):
			edge_dict = {}
			for edge in edge_list:
				subj,_,_ = edge
				subj_key = key_fn(subj)
				if subj_key not in edge_dict:
					edge_dict[subj_key] = []
				edge_dict[subj_key].append(edge)
			return edge_dict
		def get_named_predicates(root_concept, edge_dict):
			named_predicates = []
			concept_checked = set()
			concept_to_check = [root_concept]
			while len(concept_to_check) > 0: # iterative version
				concept = concept_to_check.pop()
				concept_key = key_fn(concept)
				concept_checked.add(concept_key)
				for _,_,obj in edge_dict.get(concept_key,[]):
					if name_fn(obj):
						named_predicates.append(obj)
					elif key_fn(obj) not in concept_checked:
						concept_to_check.append(obj)
			return list(unique_everseen(named_predicates))

		edge_dict = build_edge_dict(edge_list, key_fn=key_fn)
		new_edge_list = []
		for edge in edge_list:
			subj,pred,obj = edge
			if not name_fn(subj):
				continue
			if name_fn(obj):
				new_edge_list.append(edge)
			else:
				new_edge_list.extend(
					(subj,pred,o)
					for o in get_named_predicates(obj, edge_dict)
				)
		return new_edge_list

	def build_concept_relation_dict(self, edge_list):
		assert False, 'Not implemented'

	def build_lattice(self, edge_list, stringify=False):
		edge_list = list(edge_list)
		concept_relation_dict = self.build_concept_relation_dict(edge_list)
		properties = set(relation for relation_set in concept_relation_dict.values() for relation in relation_set)
		objects = set(concept_relation_dict.keys())
		if len(properties)==0 or len(objects)==0:
			return []
		bools = [
			[
				p in concept_relation_dict[object]
				for p in properties
			]
			for object in objects
		]

		formal_concept_context = Context(objects, properties, bools)
		self.formal_concept_context_list.append(formal_concept_context)
		concept_lattice = formal_concept_context.lattice
		
		#print(concept_lattice['person',])
		#print(concept_lattice['employer',])
		#concept_lattice.graphviz(view=True)
		#for extent, intent in concept_lattice:
		#	print('%r %r' % (extent, intent))

		for concept in concept_lattice._concepts:
			concept.objects = sorted(concept.objects)
			concept.properties = sorted(concept.properties)
		get_concept_obj = lambda x: x.objects if len(x.objects)>0 else x.index

		lattice_edge_list = []
		for concept in concept_lattice._concepts:
			concept_obj = get_concept_obj(concept)
			lattice_edge_list.extend(
				(
					concept_obj, 
					neighbor.properties, 
					get_concept_obj(neighbor),
				)
				for neighbor in concept.lower_neighbors
			)
		'''
		non_root_concept_set = set(get_concept_key(obj) for _,_,obj in lattice_edge_list)
		lattice_edge_list.extend(
			(
				'', 
				concept.properties, 
				get_concept_obj(concept),
			)
			for concept in concept_lattice._concepts
			if get_concept_key(concept) not in non_root_concept_set
		)
		'''
		is_iter = lambda element: isinstance(element, (list,tuple))
		lattice_edge_list = self.deanonymize_graph(lattice_edge_list, name_fn=lambda x: is_iter(x), key_fn=lambda x: ','.join(x) if is_iter(x) else x)
		#lattice_edge_list = list(map(lambda x: (x[-1],x[-2],x[-3]), lattice_edge_list))
		if stringify:
			list_to_string = lambda x: ', '.join(x)
			lattice_edge_list = map(lambda x: (list_to_string(x[0]), list_to_string(x[1]), list_to_string(x[2])), lattice_edge_list)
		return list(lattice_edge_list)

class ActivePredicateTypingLatticeBuilder(LatticeBuilder):
	def build_concept_relation_dict(self, edge_list):
		concept_relation_dict = {}
		for subj,pred,obj in edge_list:
			if subj not in concept_relation_dict:
				concept_relation_dict[subj] = set()
			concept_relation_dict[subj].add(f'that can {pred} is' if self.templatize else pred) # objects and properties cannot overlap
		return concept_relation_dict

class PassivePredicateTypingLatticeBuilder(LatticeBuilder):
	def build_concept_relation_dict(self, edge_list):
		concept_relation_dict = {}
		for subj,pred,obj in edge_list:
			if obj not in concept_relation_dict:
				concept_relation_dict[obj] = set()
			concept_relation_dict[obj].add(f'that can be {pred}-ed is' if self.templatize else pred) # objects and properties cannot overlap
		return concept_relation_dict

class PassiveActivePredicateTypingLatticeBuilder(LatticeBuilder):
	def __init__(self, templatize=True):
		super().__init__(templatize)
		self.active_lb = ActivePredicateTypingLatticeBuilder()
		self.passive_lb = PassivePredicateTypingLatticeBuilder()

	def build_concept_relation_dict(self, edge_list):
		concept_relation_dict = self.active_lb.build_concept_relation_dict(edge_list)
		for key,value in self.passive_lb.build_concept_relation_dict(edge_list).items():
			if key not in concept_relation_dict:
				concept_relation_dict[key] = set()
			concept_relation_dict[key] |= value
		return concept_relation_dict

class ActiveActionTypingLatticeBuilder(LatticeBuilder):
	def build_concept_relation_dict(self, edge_list):
		concept_relation_dict = {}
		for subj,pred,obj in edge_list:
			if subj not in concept_relation_dict:
				concept_relation_dict[subj] = set()
			concept_relation_dict[subj].add(f'that can {pred} {obj} is' if self.templatize else (pred,obj)) # objects and properties cannot overlap
		return concept_relation_dict

	def build_lattice(self, edge_list, stringify=False):
		edge_list = list(edge_list)
		predicate_dict = {}
		for edge in edge_list:
			subj,pred,obj = edge
			if pred not in predicate_dict:
				predicate_dict[pred] = []
			predicate_dict[pred].append(edge)

		global_lattice_edge_list = []
		for pred, new_edge_list in predicate_dict.items():
			global_lattice_edge_list += super().build_lattice(new_edge_list, stringify)
		return global_lattice_edge_list

class PassiveActionTypingLatticeBuilder(ActiveActionTypingLatticeBuilder):
	def build_concept_relation_dict(self, edge_list):
		concept_relation_dict = {}
		for subj,pred,obj in edge_list:
			if obj not in concept_relation_dict:
				concept_relation_dict[obj] = set()
			concept_relation_dict[obj].add(f'that can be {pred}-ed by {subj} is' if self.templatize else (pred,subj)) # objects and properties cannot overlap
		return concept_relation_dict

class PassiveActiveActionTypingLatticeBuilder(ActiveActionTypingLatticeBuilder):
	def __init__(self, templatize=True):
		super().__init__(templatize)
		self.active_lb = ActiveActionTypingLatticeBuilder()
		self.passive_lb = PassiveActionTypingLatticeBuilder()

	def build_concept_relation_dict(self, edge_list):
		concept_relation_dict = self.active_lb.build_concept_relation_dict(edge_list)
		for key,value in self.passive_lb.build_concept_relation_dict(edge_list).items():
			if key not in concept_relation_dict:
				concept_relation_dict[key] = set()
			concept_relation_dict[key] |= value
		return concept_relation_dict
