// create a graph class 
class DirectedGraph { 
	// defining vertex array and 
	// adjacent list 
	constructor() 
	{ 
		this.AdjacencyList = new Map();
		this.InverseAdjacencyList = new Map();
	}
	
	// add edge to the graph 
	addEdge(v, w) 
	{
		if (!this.AdjacencyList.has(v)) // initialize the adjacent list with an empty array
			this.AdjacencyList.set(v, [])
		this.AdjacencyList.get(v).push(w);

		if (!this.InverseAdjacencyList.has(w)) // initialize the adjacent list with an empty array
			this.InverseAdjacencyList.set(w, [])
		this.InverseAdjacencyList.get(w).push(v);
	}

	getRoots()
	{
		var root_set = new Set(Array.from(this.AdjacencyList.keys()))
		for (var [source,target_list] of this.AdjacencyList.entries())
		{
			for (var target of target_list) 
				if (source != target)
					root_set.delete(target)
		}
		return Array.from(root_set)
	}

	getLeaves()
	{
		var root_set = new Set(Array.from(this.InverseAdjacencyList.keys()))
		for (var [source,target_list] of this.InverseAdjacencyList.entries())
		{
			for (var target of target_list)
			{
				if (source != target)
					root_set.delete(target)
			}
		}
		return Array.from(root_set)
	}
	
	// Prints the vertex and adjacency list 
	printGraph() 
	{ 
		// get all the vertices 
		var get_keys = this.AdjacencyList.keys(); 
	  
		// iterate over the vertices 
		for (var i of get_keys) { 
			// great the corresponding adjacency list 
			// for the vertex 
			var get_values = this.AdjacencyList.get(i); 
			var conc = ""; 
	  
			// iterate over the adjacency list 
			// concatenate the values into a string 
			for (var j of get_values) 
				conc += j + " "; 
	  
			// print the vertex and its adjacency list 
			console.log(i + " -> " + conc); 
		} 
	} 
}

function get_taxonomy_information(information_uri)
{
	//console.log(information_uri)
	var query = [
		"SELECT DISTINCT ?subject ?predicate ?object WHERE {",
			"<"+information_uri+"> rdfs:subClassOf* ?subject.",
			"?subject ?predicate ?object.",
		"}",
	].join("\n");
	//console.log(query)
	var query_result = query_sparql_endpoint(DBPEDIA_ENDPOINT, query)
	if (!query_result || !query_result.results || query_result.results.bindings.length==0)
		return null
	var tuple_list = query_result.results.bindings
	// Build subject map
	var subj_map = new Map()
	for (tuple of tuple_list)
	{
		var subj = tuple.subject.value, pred = tuple.predicate.value, obj = tuple.object.value
		if (!subj_map.has(subj))
			subj_map.set(subj, {'@id': subj})
		subj_map.get(subj)[tuple.predicate.value] = tuple.object.value
	}
	function recursive_graph_building(subj) {
		var jsonld_graph = Object.assign({}, subj_map.get(subj));
		for (var [key,value] of Object.entries(jsonld_graph))
		{
			if (key=='@id')
				continue
			if (subj_map.has(value) && value!=subj)
				jsonld_graph[key] = recursive_graph_building(value)
		}
		return jsonld_graph
	}
	var jsonld_graph = recursive_graph_building(information_uri)
	// console.log(jsonld_graph)
	var ground = {
		'@type': 'JSON',
		'@value': JSON.stringify(query_result, null, 2)
	}
	jsonld_graph = format_jsonld(jsonld_graph, ground, query)
	return jsonld_graph
}
//console.log(get_taxonomy_information('http://dbpedia.org/class/yago/WikicatNeuralNetworks'))

function get_typeset_hierarchy_leaves_from_dbpedia(type_list) 
{
	if (type_list.length == 1)
		return type_list
	var type_query = []
	for (var type of type_list)
	{
		if (type_query.length > 0)
			type_query.push('UNION')
		type_query.push(
			[
				"{",
					"SELECT DISTINCT ?class ?superclass WHERE {",
						"<"+type+"> rdfs:subClassOf* ?class.",
						"?class rdfs:subClassOf? ?superclass.",
					"}",
				"}"
			].join("\n")
		)
	}
	// console.log(PREFIX_MAP_STRING)
	var query = [
		PREFIX_MAP_STRING,
		"SELECT DISTINCT ?class ?superclass WHERE {",
			type_query.join("\n"),
		"}"
	].join("\n");
	// console.log(query)

	function get_leaves(_data) 
	{
		// console.log(_data)
		var results = _data.results.bindings;
		var class_hierarchy = new DirectedGraph()
		for (var i in results) 
		{
			var row = results[i]
			var super_class = row['superclass'].value
			var sub_class = row['class'].value;
			class_hierarchy.addEdge(super_class, sub_class);
		}
		// console.log(class_hierarchy.getLeaves())
		return class_hierarchy.getLeaves()
	}
	return get_leaves(query_sparql_endpoint(DBPEDIA_ENDPOINT, query));
}

function build_minimal_type_graph(minimal_entity_graph, predicate=TYPE_URI, collector=HAS_ENTITY_URI)
{
	// minimal_entity_graph = format_jsonld(minimal_entity_graph);
	var entity_dict = get_entity_dict(minimal_entity_graph);
	var tot_statement_count = count_graph_statements(minimal_entity_graph);
	minimal_entity_graph = get_URI_graph(minimal_entity_graph, predicate, collector, recursion=false);
	// Create the entity_type_map, in order to easily keep track of entities and their types
	var type_rdfitem_map = new Map();
	var entity_type_map = new Map();
	for (var sub_graph of minimal_entity_graph)
	{ 
		var type = sub_graph['@id']['@value'];
		type_rdfitem_map.set(type, sub_graph['@id']);
		var sub_graph_list = isArray(sub_graph[collector]) ? sub_graph[collector] : [sub_graph[collector]];
		for (var g of sub_graph_list)
		{
			if (jQuery.isEmptyObject(g))
				continue;
			var entity_id = g['@id']['@value']
			if (!entity_type_map.has(entity_id))
			{
				entity_type_map.set(entity_id, {})
				entity_type_map.get(entity_id)[TYPESET_URI] = new Set()
				entity_type_map.get(entity_id)[collector] = g
			}
			entity_type_map.get(entity_id)[TYPESET_URI].add(type)
		}
	}
	// Remove redundant types from the entity_type_map.
	// Redundant types are those types that can be inferred from the other types, following superclass relations in dbpedia.
	// for (var [entity_id, type_dict] of entity_type_map.entries())
	// {
	// 	var redundant_type_set = new Set(type_dict[TYPESET_URI])
	// 	var type_hierarchy_leaves = get_typeset_hierarchy_leaves_from_dbpedia(Array.from(redundant_type_set))
	// 	if (type_hierarchy_leaves.length == 0) // entity not found in dbpedia
	// 		continue
	// 	for (var minimal_type of type_hierarchy_leaves)
	// 		redundant_type_set.delete(minimal_type)
	// 	//console.log(entity_id, redundant_type_set)
	// 	for (var redundant_type of redundant_type_set)
	// 		type_dict[TYPESET_URI].delete(redundant_type)
	// }
	// Create the type_entity_map, merging similar type groups
	var type_entity_map = new Map();
	var current_type_group_id = 0;
	for (var [entity_id, type_dict] of entity_type_map.entries())
	{
		var minimal_type_list = Array.from(type_dict[TYPESET_URI])
		if (minimal_type_list.length==0)
			continue
		var type_id = minimal_type_list.sort().join(' ')
		minimal_type_list = minimal_type_list.map(x => type_rdfitem_map.get(x)) // recover grounds
		if (!type_entity_map.has(type_id))
		{
			if (minimal_type_list.length==1) 
			{
				var type_uri_item = minimal_type_list[0];
				var type_graph = {'@id': type_uri_item};
				// type_graph[ENTITY_PERCENTAGE_URI] = build_RDF_item(0);
				type_graph[STATEMENT_COUNT_URI] = build_RDF_item(0);
				// type_graph[ENTITY_COUNT_URI] = build_RDF_item(0);
				// var class_information = get_taxonomy_information(type_uri_item['@value']);
				// if (class_information!==null) // build domain stage
				// 	type_graph[PROPERTY_LIST_URI] = class_information;
				type_entity_map.set(type_id, type_graph);
			}
			else 
			{
				var class_set = []
				for (var type_uri_item of minimal_type_list)
				{
					class_set.push(Object.assign({}, 
						{'@id': type_uri_item},
						entity_dict[type_uri_item['@value']], 
						// get_taxonomy_information(type_uri_item['@value'])
					));
				}
				if (class_set.length > 0)
					class_set = class_set.filter(x=>x['@id']['@value']!=PREFIX_MAP['owl']+'Thing');
				var type_entity_dict = {};
				type_entity_dict['@id'] = build_RDF_item('my:CompositeClass'+current_type_group_id);
				type_entity_dict[IS_COMPOSITE_CLASS_BOOL_URI] = build_RDF_item(true);
				// type_entity_dict[ENTITY_PERCENTAGE_URI] = build_RDF_item(0);
				type_entity_dict[STATEMENT_COUNT_URI] = build_RDF_item(0);
				// type_entity_dict[ENTITY_COUNT_URI] = build_RDF_item(0);
				// type_entity_dict[CLASS_COUNT_URI] = build_RDF_item(class_set.length);
				type_entity_dict[COMPOSITE_CLASS_SET_URI] = class_set;
				type_entity_map.set(type_id, type_entity_dict);
				current_type_group_id += 1;
			}
			type_entity_map.get(type_id)[collector] = [];
		}
		type_entity_map.get(type_id)[collector].push(type_dict[collector]);
	}
	// Return a new minimized type graph
	var type_entity_dict_list = Array.from(type_entity_map.values());
	for (var i in type_entity_dict_list)
	{
		var type_entity_dict = type_entity_dict_list[i];
		var type_uri = type_entity_dict['@id']['@value'];
		var type_statement_count = count_graph_statements(type_entity_dict[collector]);
		// type_entity_dict[ENTITY_PERCENTAGE_URI] = build_RDF_item(String((100*type_statement_count/tot_statement_count).toFixed(2))+'%');
		type_entity_dict[STATEMENT_COUNT_URI] = build_RDF_item(type_statement_count);
		// type_entity_dict[ENTITY_COUNT_URI] = build_RDF_item(type_entity_dict[collector].length);
		if (type_uri in entity_dict)
			type_entity_dict_list[i] = Object.assign({}, type_entity_dict, entity_dict[type_uri]);
	}
	// Sort by entity count
	var minimal_type_graph = type_entity_dict_list.sort((a,b)=>b[STATEMENT_COUNT_URI]['@value']-a[STATEMENT_COUNT_URI]['@value']);
	// Add type info to entities that are also types
	for (var type_dict of minimal_type_graph)
	{
		if (!(LABEL_URI in type_dict))
			type_dict[LABEL_URI] = format_link(get_dict_description(type_dict), false);
		// console.log(type_dict, (collector in type_dict))
		if (!(collector in type_dict))
			continue;
		for (var ent_dict of type_dict[collector])
		{
			var ent_id = ent_dict['@id']['@value'];
			if (!type_entity_map.has(ent_id))
				continue;
			// console.log(ent_id);
			for (var [k,v] of Object.entries(type_entity_map.get(ent_id)))
				ent_dict[k] = v;
		}
	}
	return minimal_type_graph;
}