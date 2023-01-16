var KNOWN_ENTITY_DICT = {};

function get_known_label(id) 
{
	id = prefixed_string_to_uri(id);
	if (id in KNOWN_ENTITY_DICT)
	{
		const desc = get_dict_description(KNOWN_ENTITY_DICT[id]);
		return isURL(desc)?format_link(desc, false):desc;
	}
	return null;
}

function get_formatted_tuple_template(is_in_array, value, single_element_fn, multiple_elements_fn, array_item_fn=null, max_length=null)
{
	if (isArray(value) && value.length == 1)
		value = value[0]
	var original_value = value;
	var is_dict = isDict(original_value);
	var is_rdf = isRDFItem(original_value);
	// if (is_in_array)
	// 	console.log(is_dict, value);

	if (is_dict)
		value = get_dict_description(value, as_label=false)
	else if (is_rdf)
		value = get_RDFItem_description(value);
	if (!isArray(value))
	{
		const value_is_url = isURL(value);
		const known_label = titlefy(get_known_label(value));
		if (value_is_url)
			value = linkify(value, known_label);
		else if (known_label)
			value = known_label;
		value = clip_text(value,max_length);
		var template = '';
		if (is_in_array)
		{
			if (array_item_fn == null)
			{
				if (value_is_url)
					array_item_fn = x=>x;
				else
					array_item_fn = x=>'«'+x+'»';
			}
			template = value?array_item_fn(value):'';
		}
		else
			template = single_element_fn(value);
		if (!template)
			return '';
		// if (is_dict)
		// 	template += ':';
		return template;
	}
	// value is Array
	return value.length==0?'':(multiple_elements_fn(value) + ':');
}

function clip_text(text, max_length)
{
	if (max_length && text.length>max_length)
		text = text.slice(0,max_length) + '[...]';
	return text;
}

function get_default_predicate_template(predicate, object, ancestor_predicate)
{
	var is_in_array = is_array_element(predicate, ancestor_predicate);
	// console.log(is_in_array, predicate, ancestor_predicate)
	if (isURL(predicate))
		predicate = linkify(predicate);
	templatized_text = get_formatted_tuple_template(is_in_array, object, 
		x=>'The <b>'+predicate+'</b> of this resource is «'+x+'»',
		x=>'The <b>'+predicate+'</b> of this resource are',
	);
	return {
		'is_in_array': is_in_array,
		'predicate_list': [predicate], 
		'text': templatized_text,
	};
}

function get_table(heads, values_list)
{
	var head_row = '';
	head_row += '<tr>'
	for (var h of heads)
		head_row += `<th>${h}</th>`;
	head_row += '</tr>'

	var value_row = '';
	for (var values of values_list)
	{
		value_row += '<tr>'
		for (var v of values)
			value_row += `<td>${v}</td>`
		value_row += '</tr>'
	}
	return `<table class="table table-bordered">${head_row}${value_row}</table>`;
}

function get_known_concepts_from_annotated_sentences(annotated_sentence_list, related_concepts_limit=null)
{
	var annotation_list_uri = prefixed_string_to_uri('my:annotationList');
	var word_annotation_list_uri = prefixed_string_to_uri('my:wordLevelAnnotationList');
	var related_to_uri = prefixed_string_to_uri('my:relatedTo');
	var relation_list = [];
	for (var annotated_sentence of annotated_sentence_list)
	{
		var annotation_list = get(annotated_sentence,annotation_list_uri,[]);
		if (word_annotation_list_uri in annotated_sentence)
		{
			var word_annotation_list = annotated_sentence[word_annotation_list_uri];
			for (var word_annotation of word_annotation_list)
				annotation_list = annotation_list.concat(word_annotation[annotation_list_uri]);
		}
		for (var annotation of annotation_list)
		{
			if (related_to_uri in annotation)
				relation_list.push(get_RDFItem_description(annotation[related_to_uri]));
		}
	}
	// display only unique relations
	relation_list = [...new Set(relation_list)];
	// keep only the first 3 elements
	if (related_concepts_limit)
		relation_list = relation_list.slice(0, related_concepts_limit);
	var result = relation_list.map(x=>linkify(x)).join(', ');
	if (relation_list.length >= related_concepts_limit)
		result += ', etc..';
	return result;
}

function try_to_apply_dict_to_template(ancestor, dict, template)
{
	var predicate_list = [];
	var value_list = [];
	var keys = template['keys'].map(prefixed_string_to_uri);
	var optional_keys = new Set(get(template, 'optional_keys', []).map(prefixed_string_to_uri));
	for (var predicate of keys) 
	{
		var predicate_found = predicate in dict;
		if (!predicate_found)
		{
			var predicate_is_optional = optional_keys.has(predicate);
			if (!predicate_is_optional)
				return null;
			value_list.push(null);
		}
		else
		{
			var object = dict[predicate];
			if (isRDFItem(object))
				object = get_RDFItem_description(object);
			// else if (isArray(object) && object.length==0)
			// 	return null;
			value_list.push(object);
			predicate_list.push(predicate);
		}
	}
	if (value_list.filter(x=>x != null).length == 0)
		return null;
	var is_in_array = false;
	if (predicate_list.length==1)
	{
		for (var k of keys) // this should handle grouped lists with different predicates (for which is_in_array is clearly true)
		{
			if (is_array_element(k, ancestor))
			{
				is_in_array = true;
				break;
			}
		}
	}
	return Object.assign({}, template, {
		'is_in_array': is_in_array,
		'predicate_list': predicate_list, 
		'keys_to_hide_as_child': get(template, 'keys_to_hide_as_child', []).map(prefixed_string_to_uri),
		'label': get(template, 'label', null),
		'text': template['template_fn'](is_in_array, ancestor, value_list),
	});
}

function is_array_element(prefixed_predicate, ancestor)
{
	return prefixed_string_to_uri(prefixed_predicate)==prefixed_string_to_uri(ancestor);
}

function get_template_list(dict, ancestor=null)
{
	var graph_templates = [];
	for (var t in TEMPLATE_LIST)
	{
		var template = TEMPLATE_LIST[t];
		var applied_template = try_to_apply_dict_to_template(ancestor, dict, template);
		if (applied_template)
		{
			applied_template['position'] = t;
			graph_templates.push(applied_template);
		}
	}
	// some templates may overlap, remove all the redundant templates (that are those for which all the parameters are contained into another template with a greater or equal number of parameters)
	var filtered_graph_templates = [];
	// sort by predicate list length
	graph_templates = graph_templates.sort((a, b) => a.predicate_list.length-b.predicate_list.length); // ascending order
	for (var k=0; k < graph_templates.length; k++)
	{
		var template_dict = graph_templates[k];
		var overlap = false;
		for (var i=k+1; !overlap && i<graph_templates.length; i++)
		{
			var other_template_dict = graph_templates[i];
			// if (other_template_dict.predicate_list.length < template_dict.predicate_list.length)
			// 	continue;
			var may_overlap = true;
			var other_predicate_set = new Set(other_template_dict['predicate_list']);
			var predicate_list = template_dict['predicate_list'];
			for (var j=0; may_overlap && j<predicate_list.length; j++)
			{
				if (!other_predicate_set.has(predicate_list[j]))
					may_overlap = false;
			}
			if (may_overlap)
				overlap = true;
		}
		if (!overlap)
			filtered_graph_templates.push(template_dict);
	}
	filtered_graph_templates = filtered_graph_templates.sort((a, b) => a.position-b.position); // ascending order
	return filtered_graph_templates;
}

function to_external_link(link, name=null)
{
	link = String(link).replace(/<|>|"/gi,'');
	if (!name)
		name = isURL(link) ? format_link(link) : link;

	return `<a href="${link}" target="_blank">${name}</a>`;
}

function linkify(link, name=null)
{
	link = String(link).replace(/<|>|"/gi,'');
	if (!name)
		name = isURL(link) ? format_link(link) : link;

	return template_expand(name,link);
}

function template_expand(name,topic=null) 
{
	if (!topic)
		topic = name
	return `<annotation><span 
				class="link"
				data-topic="${topic}"
			>${name}</span></annotation>`;
}

function counterfactual_input(counterfactual_api_url, feature_order, value)
{
	return `<input 
				class="counterfactual" 
				id="${feature_order}" 
				data-api="${counterfactual_api_url}" 
				value="${value}"
				type="number" 
			>`;
}
