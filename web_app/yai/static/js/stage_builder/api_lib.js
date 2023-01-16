const API_SERVER_URL = location.protocol+'//'+location.hostname+(location.port ? ':'+location.port: '')+'/';

function expand_information(information_uri, known_entity_dict, language='en', use_linksum=true, retry=true)
{
	if (information_uri in known_entity_dict)
		return Object.assign({},known_entity_dict[information_uri]);

	var query = ''
	if (use_linksum) // LinkSUM: Using Link Analysis to Summarize Entity Data
	{
		query = [
			PREFIX_MAP_STRING,
			"SELECT ?v ?predicate ?object",
			"FROM <http://dbpedia.org>",
			"FROM <http://people.aifb.kit.edu/ath/#DBpedia_PageRank>",
			"WHERE {",
				"{", // show abstract, label and type first
					"SELECT ?predicate ?object WHERE {",
						"<"+information_uri+"> ?predicate ?object.",
						"FILTER(?predicate = dbo:abstract || ?predicate = rdfs:label || ?predicate = rdf:type).",
						"FILTER(!isLiteral(?object) || lang(?object) = '' || langMatches(lang(?object), '"+language+"')).",
					"}",
					"ORDER BY DESC(?predicate)",
				"} UNION {", // show subclasses
					"SELECT (my:superClassOf AS ?predicate) ?object WHERE {",
						"?object rdfs:subClassOf <"+information_uri+">.",
						"FILTER(!isLiteral(?object) || lang(?object) = '' || langMatches(lang(?object), '"+language+"')).",
					"}",
				"} UNION {", // show other properties second, ranked by importance
					"SELECT ?predicate ?object ?v WHERE {",
						"<"+information_uri+"> ?predicate ?object.",
						"FILTER(!isLiteral(?object) || lang(?object) = '' || langMatches(lang(?object), '"+language+"')).",
						"FILTER(?predicate != rdfs:comment && ?predicate != vrank:hasRank && ?predicate != dbo:abstract && ?predicate != rdfs:label && ?predicate != rdf:type).",
						"OPTIONAL {?object vrank:hasRank ?r. ?r vrank:rankValue ?v}.",
					"}",
					"ORDER BY DESC(?v), DESC(?predicate)",
				"}",
			"}",
		].join("\n")
	}
	else
	{
		query = [
			"SELECT DISTINCT ?predicate ?object WHERE {",
				"<"+information_uri+"> ?predicate ?object.",
				"FILTER(!isLiteral(?object) || lang(?object) = '' || langMatches(lang(?object), '"+language+"')).",
			"}",
		].join("\n");
	}
	var query_result = query_sparql_endpoint(DBPEDIA_ENDPOINT, query)
	if (!query_result || !query_result.results || query_result.results.bindings.length==0)
	{
		if (!retry)
			return null;
		return expand_information(PREFIX_MAP['dbr']+getPath(information_uri), known_entity_dict, language, use_linksum, false);
	}
	// console.log(query_result)
	// Build subject map
	var jsonld_graph = {'@id':information_uri}
	for (tuple of query_result.results.bindings)
	{
		var pred = tuple.predicate?String(tuple.predicate.value):'';
		if (pred == '')
			continue
		var obj = tuple.object?String(tuple.object.value):'';
		if (pred in jsonld_graph)
		{
			if (!isArray(jsonld_graph[pred]))
				jsonld_graph[pred] = [jsonld_graph[pred]]
			jsonld_graph[pred].push(obj)
		}
		else
			jsonld_graph[pred] = obj
	}
	var ground = {
		'@type': 'JSON',
		'@value': JSON.stringify(query_result, null, 2)
	}
	var formatted_jsonld_graph = format_jsonld(jsonld_graph, ground, query);
	return formatted_jsonld_graph;
}

function expand_link(link, show_expansion_fn, known_entity_dict)
{
	try {
		if (!isURL(link)) // query wikipedia
			query_wikipedia_by_title(link, show_expansion_fn)
		else
		{ // query dbpedia
			console.log('Expanding '+format_link(link)+' on DBPedia.');
			var response = expand_information(link, known_entity_dict);
			if (response)
				response['@id'] = link;
			show_expansion_fn(response);
		}
	} catch (ex) {
		if (DEBUG)
			console.error(ex);
	}
}

function generate_counterfactual(information_dict)
{
	var api = information_dict['api'];
	var input = information_dict['input'].map(x=>parseInt(x,10));
	var output = null;
	try {
		$.ajax({
			url:api, 
			// async: false,
			method:'POST',
			async: false,
			data: JSON.stringify({'sample_value': input}),
			contentType: "application/json; charset=utf-8",
			success: x => output=x,
		});
	} catch(e) {
		if (DEBUG)
			console.error(e);
	}
	return output;
}

function get_counterfactual(current, api, process_graph)
{
	var process_input_dict = get_process_input_dict_from_formatted_jsonld({'my:processList':process_graph});
	var input_list = [].concat(...Object.values(process_input_dict).filter(x=>x[0][COUNTERFACTUAL_API_URI] == api));	
	var input_values = $(".counterfactual").toArray().sort((a, b) => get_DOM_element_distance(a,current) - get_DOM_element_distance(b,current));
	input_values = input_values.concat(input_list.map(x=>{
		return {'id':x[FEATURE_ORDER_URI],'value':x[VALUE_URI]}
	}));
	input_values = get_unique_elements(input_values, x=>x.id);
	return input_values.sort((a, b) => parseInt(a.id) - parseFloat(b.id)).map(x=>x.value);
}

function get_typed_entity_dict_from_jsonld(jsonld)
{
	var minimal_entity_graph = build_minimal_entity_graph(jsonld);
	var minimal_subclass_graph = build_minimal_type_graph(minimal_entity_graph, SUBCLASSOF_URI, HAS_SUBCLASS_URI);
	var minimal_type_graph = build_minimal_type_graph(minimal_entity_graph, TYPE_URI, HAS_ENTITY_URI);
	return get_entity_dict(minimal_entity_graph.concat(minimal_type_graph).concat(minimal_subclass_graph));
}

function get_entity_dict_from_jsonld(jsonld)
{
	return get_entity_dict(build_minimal_entity_graph(jsonld));
}

function format_dataset(data, id=null)
{
	var dataset = {};
	var fragments_count = isArray(data)?data.length:1;
	console.log('RDF Fragments count:', fragments_count);
	if (fragments_count==0)
		return dataset;

	if (isDict(data) && '@id' in data)
		dataset['@id'] = data['@id'];
	if (id)
	{
		dataset[LABEL_URI] = build_RDF_item(id);
		console.log('Formatting dataset:', id);
	}
	else
		console.log('Formatting dataset:', dataset['@id']);

	// Get entity-centered graph
	var minimal_entity_graph = build_minimal_entity_graph(data);
	console.log('Entity count:', data.length)
	// Get class-centerd graph
	var minimal_type_graph = build_minimal_type_graph(minimal_entity_graph)
	console.log('Class count:', minimal_type_graph.length)
	dataset[STATEMENT_COUNT_URI] = build_RDF_item(count_graph_statements(minimal_entity_graph))
	dataset[ENTITY_COUNT_URI] = build_RDF_item(minimal_entity_graph.length)
	dataset[CLASS_COUNT_URI] = build_RDF_item(minimal_type_graph.length)
	dataset[CLASS_LIST_URI] = minimal_type_graph
	return dataset
}
