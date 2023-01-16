SCHEMA = 'https://schema.org/'

function extract_entity_by_type_list(type_list, graph)
{
	if (isArray(graph))
	{
		var process_list = [];
		var new_graph = [];
		for (var g of graph)
		{
			var [extracted_processes, new_g] = extract_entity_by_type_list(type_list, g);
			if (extracted_processes.length > 0)
				process_list = process_list.concat(extracted_processes);
			if (new_g)
				new_graph.push(new_g);
		}
		if (new_graph.length == 0)
			new_graph = null;
		return [process_list,new_graph];
	}
	else if (isDict(graph))
	{
		if (TYPE_URI in graph && type_list.includes(graph[TYPE_URI]['@value']))
			return [[graph],null];
		
		var process_list = [];
		var new_graph = {};
		for (var [k,g] of Object.entries(graph))
		{
			var [extracted_processes, new_g] = extract_entity_by_type_list(type_list,g);
			process_list = process_list.concat(extracted_processes);
			new_graph[k] = new_g?new_g:g['@id'];
		}
		return [process_list,new_graph];
	}
	return [[],Object.assign({},graph)];
}

function get_URI_graph(graph, key, collector, recursion=true, is_first=true, class_ground=new Map()) 
{
	function merge_URI_dict(a,b) {
		for (var [class_name, graph_list] of Object.entries(b))
		{
			if (!(class_name in a))
				a[class_name] = []
			a[class_name] = a[class_name].concat(b[class_name])
		}
		return a
	}
	function add_unknown_graph_to_dict(n,d) {
		if (!(UNKNOWN_TYPE_URI in d))
			d[UNKNOWN_TYPE_URI] = []
		d[UNKNOWN_TYPE_URI].push(n)
	}
	var class_dict = {}
	if (isArray(graph))
	{
		for (var i in graph)
		{
			new_class_dict = get_URI_graph(graph[i], key, collector, recursion, false, class_ground)
			class_dict = merge_URI_dict(class_dict, new_class_dict)
			if (is_first && Object.keys(new_class_dict).length==0)
				add_unknown_graph_to_dict(graph[i],class_dict)
		}
	}
	else if (isDict(graph))
	{
		if (key in graph)
		{
			var graph_key_list = (!isArray(graph[key]))?[graph[key]]:graph[key]
			for (var i in graph_key_list) 
			{
				var class_name = graph_key_list[i]['@value']
				if (!isURL(class_name))
				{
					var context = ('@context' in graph)?graph['@context']['@value']:SCHEMA
					//console.log(graph['@context'],graph_key_list[i])
					if (context!='')
						class_name = pathJoin([context,class_name])
				}
				if (!(class_name in class_dict))
					class_dict[class_name] = []
				graph = Object.assign({},graph) // deep copy
				//delete graph[key]
				class_dict[class_name].push(graph)
				class_ground.set(class_name, graph_key_list[i]['@ground'])
			}
		}
		else if (is_first)
			add_unknown_graph_to_dict(graph,class_dict)

		if (recursion)
		{
			for (var tuple of Object.entries(graph)) 
			{
				if (tuple[0] == key)
					continue
				var object_list = tuple[1]
				//console.log(object_list, get_URI_graph(object_list, key, collector, recursion, false))
				class_dict = merge_URI_dict(class_dict, get_URI_graph(object_list, key, collector, recursion, false, class_ground))
			}
		}
	}
	if (!is_first)
		return class_dict

	var class_list = []
	for (var [class_name, type_graph] of Object.entries(class_dict)) 
	{
		var class_dict = {}
		class_dict['@id'] = build_RDF_item(class_name, class_ground.get(class_name))
		class_dict[collector] = type_graph
		class_list.push(class_dict)
	}
	return class_list
}

function assign_unique_ids_to_graph(graph, anonymous_node_count=0, id_base='') 
{
	if (isArray(graph))
	{
		for (var i in graph)
			anonymous_node_count = assign_unique_ids_to_graph(graph[i], anonymous_node_count, id_base);
	}
	else if (isDict(graph))
	{
		if (!('@id' in graph))
		{
			graph['@id'] = build_RDF_item(`my:AnonymousEntity_${id_base}_${anonymous_node_count}`);
			anonymous_node_count += 1;
		}
		for (var [key,value] of Object.entries(graph))
			anonymous_node_count = assign_unique_ids_to_graph(value, anonymous_node_count, id_base);
	}
	return anonymous_node_count;
}

function build_minimal_entity_graph(graph) 
{
	// graph = format_jsonld(graph)
	var new_graph_list = []
	// Assign unique ids
	assign_unique_ids_to_graph(graph);
	// Get entity dict
	var graph_list = get_URI_graph(graph, '@id', HAS_ENTITY_URI)
	// Merge graphs with same entity
	for (var ent_idx in graph_list)
	{
		var entity_id = graph_list[ent_idx]['@id']
		var entity_graph_list = graph_list[ent_idx][HAS_ENTITY_URI]
		// keep the biggest graph as central graph and merge the others, this would help keeping grounds as less redundant as possible
		entity_graph_list.sort(function(a, b){
		  // ASC  -> a.length - b.length
		  // DESC -> b.length - a.length
		  return b.length - a.length;
		});

		var entity_graph = entity_graph_list[0] // keep the biggest graph as central graph and merge the others
		for (var i=1; i<entity_graph_list.length; ++i)
		{
			var current_entity_graph = entity_graph_list[i]
			for (var [pred, obj] of Object.entries(current_entity_graph))
			{
				if (pred == '@id')
					continue
				if (pred in entity_graph)
				{ // create list
					var original_obj = entity_graph[pred]
					if (isDict(original_obj) || !isArray(original_obj))
						entity_graph[pred] = [original_obj]
					entity_graph[pred].push(obj)
				}
				else
					entity_graph[pred] = obj
			}
		}
		// Remove duplicates
		for (var [pred, obj] of Object.entries(entity_graph))
		{
			if (isArray(obj))
			{
				//console.log('pre',obj)

				obj = get_unique_elements(obj, function(x) {
					if (isArray(x))
						return get_array_description(x);
					if (isDict(x))
						return get_dict_description(x);
					return get_RDFItem_description(x);
				});
				if (obj.length == 1)
					obj = obj[0];
				entity_graph[pred] = obj;
			}
		}
		new_graph_list.push(entity_graph);
	}
	return new_graph_list;
}

function get_entity_dict(graph)
{
	var entity_dict = {};
	for (var known_entity of graph)
	{
		if ('@id' in known_entity)
		{
			var key = known_entity['@id']['@value'];
			if (!(key in entity_dict))
				entity_dict[key] = {};
			Object.assign(entity_dict[key], known_entity);
		}
	}
	return entity_dict;
}

function count_graph_statements(graph)
{
	var count = 0
	if (isArray(graph))
	{
		for (var g of graph)
			count += count_graph_statements(g);
	}
	else if (isDict(graph))
	{
		for (var [pred, obj] of Object.entries(graph))
		{
			if (pred == '@id')
				continue
			if (isArray(obj))
				count += obj.length
			count += 1 + count_graph_statements(obj)
		}
	}
	return count
}

function sort_graph(graph)
{
	function is_special(k){return k.startsWith('@') || k=='type'}
	function is_relevant(k){return ['abstract','label'].includes(k)}
	function abstract_comparison(fun,a,b) {
		if (fun(a) && !fun(b))
			return -1;
		if (!fun(a) && fun(b))
			return 1;
		if (fun(a) && fun(b))
			return 0;
		return null
	}

	if (isDict(graph))
	{
		// Create items array
		var items = Object.keys(graph).map(key => [key, graph[key]]);
		// Sort the array based on the second element
		items = items.sort(function(a, b){
			var a=isURL(a[0])?getPath(a[0]):a[0], b=isURL(b[0])?getPath(b[0]):b[0]
			// put special elements first
			special_comparison = abstract_comparison(is_special,a,b)
			if (special_comparison !== null)
				return special_comparison
			// put relevant elements second
			relevant_comparison = abstract_comparison(is_relevant,a,b)
			if (relevant_comparison !== null)
				return relevant_comparison
			// put remaining elements last
			if(a < b) 
		    	return -1;
		    if(a > b) 
		    	return 1;
		    return 0;
		});
		//console.log(items)
		var ordered_graph = {}
		for (var [k,v] of items)
			ordered_graph[k]=sort_graph(v)
		graph = ordered_graph
	}
	else if (isArray(graph))
	{
		//var items = Object.keys(graph).map(e => getPath(e['@id']));
		for (var i in graph)
			graph[i] = sort_graph(graph[i])
	}
	return graph
}
