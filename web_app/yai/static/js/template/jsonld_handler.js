function get_predicate_templatized_label(ancestor, predicate, data)
{
	var predicate_data = {};
	predicate_data[predicate] = data;
	var templatized_text_list = get_template_list(predicate_data, ancestor);
	if (templatized_text_list.length > 0)
		return templatized_text_list[0];
	return get_default_predicate_template(predicate, data, ancestor);
}

function annotate_nestedlist(nested_tree, annotation_list, annotation_fn) {
	if (isArray(nested_tree))
		nested_tree.map(c=>annotate_nestedlist(c, annotation_list, annotation_fn));
	else
	{
		nested_tree.text = annotate_hmtl(nested_tree.text, annotation_list, annotation_fn);
		// console.log(nested_tree.text);
		if (nested_tree.children && nested_tree.children.length)
			nested_tree.children.map(c=>annotate_nestedlist(c, annotation_list, annotation_fn));
	}
	return nested_tree
}

function nest_jsonld(data, uri_dict, ignore_set=null, max_depth=null, parent_set=null, depth=0)
{
	parent_set = new Set(parent_set);
	ignore_set = new Set(ignore_set);
	// Replace using uri dict
	if (isRDFItem(data))
	{
		var desc = get_RDFItem_description(data);
		if (ignore_set.has(desc))
			return data;
		const is_url = isURL(desc);
		if (is_url && parent_set.has(desc))
			return data;
		if (!(desc in uri_dict))
			return data;
		data = uri_dict[desc];
		if (is_url && isDict(data))
		{
			const data_uri = get_description(data, false);
			const data_label = get_description(data);
			data = {'@id': build_RDF_item(data_uri)}
			if (data_uri!=data_label)
				data[LABEL_URI] = build_RDF_item(data_label);
			return data;
		}
		depth += 1;
		if (max_depth && depth > max_depth)
			return data;
	}
	if (isArray(data))
		return data.map(x=>nest_jsonld(x, uri_dict, ignore_set, max_depth, parent_set, depth));
	if (isDict(data))
	{
		var new_data = {}
		for (var [k,v] of Object.entries(data))
		{
			if (k == '@id')
			{
				parent_set.add(get_RDFItem_description(v));
				new_data[k] = v;
				continue;
			}
			const v_desc = get_description(v, false);
			if (ignore_set.has(v_desc))
				new_data[k] = build_RDF_item(v_desc);
			else
				new_data[k] = nest_jsonld(v, uri_dict, ignore_set, max_depth, parent_set, depth);
		}
		return new_data;
	}
	return data;
}

function jsonld_to_nestedlist(data, depth=0, predicate=null, ancestor=null) // Display JSON-LD data as a HTML tree view
{
	var node_id = depth + 1;
	var is_first = depth==0;
	var current_depth = depth;
	// Define routine/goto to get a fragment
	function get_fragment(o, p, ancestor_p) { // local function, keep it local
		node_id = depth + 1;
		var sub_tree_dict = null;
		[sub_tree_dict, depth] = jsonld_to_nestedlist(o, node_id, p, ancestor_p);
		return sub_tree_dict
	}
	// Avoid useless nesting
	if (isArray(data) && data.length==1)
		data = data[0];
	// // Get predicate
	// if (predicate === null)
	// 	predicate = 'Document';

	// Get tree text and predicate link
	var tree_dict = get_predicate_templatized_label(ancestor, predicate, data);
	// Build html fragment
	if (isDict(data))
	{
		// add children
		var child_list = [];
		var already_processed_predicates = [];
		// get templatized text list
		var template_list = get_template_list(data, ancestor);
		for (var template_dict of template_list)
		{
			already_processed_predicates = already_processed_predicates.concat(template_dict['predicate_list']);
			// create new child
			var new_child = template_dict;
			// add children
			if (!template_dict['hide_descendants'])
			{
				var sub_child_list = [];
				for (var p of template_dict['predicate_list'])
				{
					if (p=='@id')
						continue;
					var object = data[p];
					
					var sub_fragment = get_fragment(object, p, p);
					if (template_dict['keys_to_hide_as_child'].includes(p) || template_dict['predicate_list'].length==1)
					{ // this predicate has been requested to be removed, by the template, save its children
						if ('children' in sub_fragment)
							sub_child_list = sub_child_list.concat(sub_fragment['children']);
					}
					else
						sub_child_list.push(sub_fragment);
				}
				if (sub_child_list.length > 0)
					new_child['children'] = sub_child_list;
			}
			// push child into child list
			child_list.push(new_child);
		}
		// process the remaining properties
		for (var [p,o] of Object.entries(data)) 
		{
			if (already_processed_predicates.includes(p))
				continue;
			if (p=='@id')
				continue;
			if (isArray(o) && o.length==0)
				continue;
			// add fragment
			child_list.push(get_fragment(o, p, predicate));
		}
		if (child_list.length > 0)
			tree_dict["children"] = child_list;
	}
	else if (isArray(data))
	{		
		var child_list = [];
		for (var i in data) // add fragment
			child_list.push(get_fragment(data[i], predicate, predicate));

		if (child_list.length > 0)
			tree_dict["children"] = child_list;
	}
	if (!is_first)
		return [tree_dict, depth];

	if (!('children' in tree_dict))
		return [];

	return flatten_single_childed_trees(clean_tree(tree_dict['children']));
}

function flatten_single_childed_trees(tree_dict_list)
{
	for (var tree_dict of tree_dict_list)
	{
		if (!('children' in tree_dict))
			continue
		if (tree_dict['children'].length == 1 && !tree_dict['is_in_array'])
		{
			var child = tree_dict['children'][0];
			if ('children' in child)
			{
				var last_char = tree_dict['text'].slice(-1);
				if (last_char == ':')
					tree_dict['text'] = tree_dict['text'].slice(0,-1)+'.';
				else if (last_char != '.')
					tree_dict['text'] += '.';
				tree_dict['text'] += ' '+child['text'];
				tree_dict['children'] = child['children'];
			}
		}
		tree_dict['children'] = flatten_single_childed_trees(tree_dict['children']);
	}
	return tree_dict_list
}

function clean_tree(tree_dict_list) 
{ // remove trees with empty text
	var new_tree_dict_list = [];
	for (var tree_dict of tree_dict_list)
	{
		tree_dict['text'] = tree_dict['text'].trim();
		if (tree_dict['children'] && tree_dict['children'].length>0)
		{
			// // array template
			// if (tree_dict['is_in_array'])
			// {
			// 	var alternative_text_list = tree_dict['children'].filter(x=>x['predicate_list'].includes('@id')).sort((a,b)=>b['predicate_list'].length-a['predicate_list'].length).map(x=>x['text']);
			// 	if (alternative_text_list.length > 0)
			// 		tree_dict['text'] = alternative_text_list[0];
			// }
			// recursive call
			tree_dict['children'] = clean_tree(tree_dict['children']);
			// remove blank nodes
			if (!tree_dict['text'])
			{
				// for (var c of tree_dict['children'])
				// 	c['label'] = tree_dict['label']
				new_tree_dict_list = new_tree_dict_list.concat(tree_dict['children']);
			}
			else
			{
				// remove children having the same text of the parent
				var new_children = [];
				const children = tree_dict['children'];
				for (var child of children)
				{
					if (child['text']==tree_dict['text'])
						new_children = new_children.concat(child['children']);
					else
						new_children.push(child);
				}
				// if (new_children.length == 1 && 'children' in new_children[0])
				// 	new_children = new_children[0]['children'];	
				tree_dict['children'] = new_children;
				new_tree_dict_list.push(tree_dict);
			}
		}
		else if (tree_dict['text'])
			new_tree_dict_list.push(tree_dict);
	}
	return new_tree_dict_list;
}
