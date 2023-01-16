TEMPLATE_LIST = [
//------------ Initial Explanation ------------
	{
		'keys': ['dbo:abstract'],
		'label': 'abstract',
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=> `<b>Abstract</b>: ${x}`,
				x=>`It has several <b>abstracts</b>`,
			)
		}
	},
	{
		'keys': ["my:has_descriptive_explanation"],
		'keys_to_hide_as_child': ["my:detail"],
		'label': 'descriptive_explanation',
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=> {
					var desc = x;
					if (isDict(value))
						desc = get_description(value[prefixed_string_to_uri("my:detail")]);
					return `<b>What does it mean?</b> ${desc}`;
				},
				x=>`<b>What does it mean?</b>`,
			)
		}
	},
	{
		'keys': ["my:has_teleological_explanation"],
		'keys_to_hide_as_child': ["my:detail"],
		'label': 'teleological_explanation',
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=> {
					var desc = x;
					if (isDict(value))
						desc = get_description(value[prefixed_string_to_uri("my:detail")]);
					return `<b>What is it for?</b> ${desc}`;
				},
				x=>`<b>What is it for?</b>`,
			)
		}
	},
	{
		'keys': ["my:has_causal_explanation"],
		'keys_to_hide_as_child': ["my:detail"],
		'label': 'causal_explanation',
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=> {
					var desc = x;
					if (isDict(value))
						desc = get_description(value[prefixed_string_to_uri("my:detail")]);
					return `<b>Why?</b> ${desc}`;
				},
				x=>`<b>Why?</b>`,
			)
		}
	},
	{
		'keys': ["my:detail"],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return value;
		}
	},
	{
		'keys': ['@id', 'my:value'],
		'hide_descendants': true,
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [id, value] = value_list;
			return `${linkify(id,get_known_label(id))}: <b>${value}</b>`;
		},
	},
	{
		'keys': ['@id', 'my:value', 'my:counterfactual_api_url'],
		'hide_descendants': true,
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [id, value, api] = value_list;
			return `${linkify(id,get_known_label(id))}: <b>${value}</b>`;
		},
	},
	{ 
		'keys': ['rdfs:seeAlso'],
		'label': 'related_to',
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`See also «${x}»`, 
				x=> {
					return `See also ${x.slice(0,1).map(y=>{
						if (isDict(y))
							return linkify(get_description(y));
						var desc = get_description(y);
						return linkify(desc, get_known_label(desc));
					}).join(', ')}, etc..`;
				},
			)
		}
	},
	{
		'keys': ["@type","my:is_based_on"],
		'keys_to_hide_as_child': ["@type","my:is_based_on"],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [type, value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=> `This ${get_known_label(type)} is <b>based on</b> ${x}`,
				x=> `This ${get_known_label(type)} is <b>based on</b>`,
			);
		},
	},
	{
		'keys': ["@type","my:takes_as_input"],
		'keys_to_hide_as_child': ["@type","my:takes_as_input"],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [type, value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=> `This ${get_known_label(type)} <b>takes as input</b> a ${x}`,
				x=> `This ${get_known_label(type)} <b>takes as input</b>`,
			);
		},
	},
	{
		'keys': ["@type","my:produces_as_output"],
		'keys_to_hide_as_child': ["@type","my:produces_as_output"],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [type, value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=> `This ${get_known_label(type)} <b>produces as output</b> a ${x}`,
				x=> `This ${get_known_label(type)} <b>produces as output</b>`,
			);
		},
	},
	{
		'keys': ["@type","my:is_made_of"],
		'keys_to_hide_as_child': ["@type","my:is_made_of"],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [type, value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=> `This ${get_known_label(type)} <b>is made of</b> ${x}`,
				x=> `This ${get_known_label(type)} <b>is made of</b>`,
			);
		},
	},
//------------ Process ------------
	{ // 'process'
		'keys': ['@type', 'my:process_output', 'my:process_input'],
		'keys_to_hide_as_child': ['@type'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [type, conclusion_list, premise_list] = value_list;
			var conclusion_count = isArray(conclusion_list)?conclusion_list.length:1;
			var premise_count = isArray(premise_list)?premise_list.length:1;
			var conclusion_label = (conclusion_count==1)?'output':'outputs';
			var premise_label = (premise_count==1)?'input':'inputs';
			return `This ${linkify(type,get_known_label(type))} has ${premise_count} ${premise_label} and ${conclusion_count} ${conclusion_label}.`;
		},
	},
	{ 
		'keys': ['my:process_input'],
		// 'keys_to_hide_as_child': ['my:process_input'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`The <b>input</b> to the process is a «${x}»`,
				x=>`The <b>inputs</b> to the process are ${x.length}`,
			)
		}
	},
	{
		'keys': ['my:process_output'],
		// 'keys_to_hide_as_child': ['my:process_output'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`The <b>output</b> of the process is a «${x}»`,
				x=>`The <b>output</b> of the process is a set of ${x.length} features`,
			);
		}
	},
	{
		'keys': ['rdfs:label', 'my:value'],
		'hide_descendants': true,
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [label, value] = value_list;
			return `The value of your «${label}» is «${value}».`;
		},
	},
	{ // 'api list'
		'keys': ['my:api_list'],
		// 'keys_to_hide_as_child': ['my:API'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`An <b>API</b> to interact with the process is ${x}`,
				x=>`Some <b>APIs</b> to interact with the process are`,
			)
		}
	},
	{ // 'process_list'
		'keys': ['my:processList'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`The <b>main automated process</b> is a ${x}. You can try to <b>change</b> its inputs`,
				x=>`The <b>automated processes</b> are the following. You can try to <b>change</b> their inputs`,
			)
		}
	},
//------------ Dataset ------------
	{
		'keys': ['my:statementCount'],
		'hide_descendants': true,
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			return ``;
		}
	},
	{ // 'label'
		'keys': ['rdfs:label'],
		// 'keys_to_hide_as_child': ['rdfs:label'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>``,
				x=>`It has several <b>names</b>`,
			)
		}
	},
	{ 
		'keys': ['dbp:link'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`It is <b>linked to</b> ${to_external_link(value,value)}`,
				x=>`It is <b>linked to</b>`,
				x=>to_external_link(value,value),
			)
		}
	},
	{ 
		'keys': ['dbo:wikiPageExternalLink'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`It is <b>linked to</b> ${to_external_link(value,value)}`,
				x=>`It is <b>linked to</b>`,
				x=>to_external_link(value,value),
			)
		}
	},
	{ // 'sub-class'
		'keys': ['rdfs:subClassOf','@type'],
		'optional_keys': ['rdfs:subClassOf','@type'],
		'label': 'class',
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [super_classes,types] = value_list;
			var supers = [];
			if (super_classes)
			{
				if (isArray(super_classes))
					supers = supers.concat(super_classes);
				else
					supers.push(super_classes);
			}
			if (types)
			{
				if (isArray(types))
					supers = supers.concat(types);
				else
					supers.push(types);
			}
			if (supers.length == 0)
				return '';
			const p = prefixed_string_to_uri;
			const hidden_classes = ["owl:Class","rdfs:Class","owl:Thing"].map(p);
			supers = supers.filter(x=>!hidden_classes.includes(p(get_description(x))));
			if (supers.length == 0)
				return '';
			if (supers.length == 1)
				supers = supers[0];
			return get_formatted_tuple_template(is_in_array, supers, 
				x=>`It <b>is a</b> ${x}`,
				x=>`It <b>is a</b>: ${get_array_description(x,1)}, etc..`,
			);
		}
	},
	{
		'keys': ['rdfs:label', 'my:statementCount', 'my:hasEntity'],
		'optional_keys': ['my:statementCount'],
		// 'expanded': true,
		'keys_to_hide_as_child': ['rdfs:label','my:statementCount', 'my:hasEntity'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [type_name, rdf_count, hasEntity] = value_list;
			if (type_name == prefixed_string_to_uri('my:Unknown'))
			{
				return get_formatted_tuple_template(is_in_array, hasEntity, 
					x=>`There is 1 <b>thing</b> that has no class: ${x}`,
					x=>`There are ${x.length} <b>things</b> that have no class`,
				);
			}
			return get_formatted_tuple_template(is_in_array, hasEntity, 
				x=>`There is 1 <b>thing</b> that is an example of ${type_name}: ${x}`,
				x=>`There are ${x.length} <b>things</b> that are an example of ${type_name}`,
			);
		}
	},
	{ // class instances
		'keys': ['my:hasEntity'],
		'label': 'class',
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`There is 1 <b>thing</b> that is an example of it: ${x}`,
				x=>`There are ${x.length} <b>things</b> that are an example of it`,
			)
		}
	},
	{
		'keys': ['rdfs:label', 'my:hasSubClass'],
		'keys_to_hide_as_child': ['rdfs:label', 'my:hasSubClass'],
		'label': 'class',
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [label,value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`There is 1 <b>example</b> of ${label}: ${x}`,
				x=>`There are ${x.length} different <b>examples</b> of ${label}`,
			)
		}
	},
	{ // derivations
		'keys': ['my:hasSubClass'],
		'label': 'class',
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`There is 1 <b>type</b> of it: ${x}`,
				x=>`There are ${x.length} different <b>types</b> of it`,
			)
		}
	},
	{ // 'class_list'
		'keys': ['my:hasClass'],
		// 'hide_descendants': true,
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`This dataset contains <b>entities</b> with type ${x}`,
				x=>`Numerically meaningful statements regard <b>entities</b> of type: ${get_array_description(x,1)}, etc...`
			)
		}
	},
	{ // 'subtype_list'
		'keys': ['my:classSet'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`The <b>sub-type</b> is ${x}`,
				x=>`The <b>sub-types</b> are`,
			)
		}
	},
	{ // 'composite_class'
		'keys': ['my:classCount', 'my:isCompositeClass', 'my:classSet'],
		'keys_to_hide_as_child': ['my:classCount', 'my:isCompositeClass', 'my:classSet'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [class_count, is_composite_class_bool, class_set] = value_list;
			return `The <b>sub-classes</b> are ${class_count}:`;
		}
	},
	{ // 'dataset_list'
		'keys': ['my:datasetList'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`The <b>main dataset</b> is «${x}»`,
				x=>`The <b>datasets</b> are the following`,
			)
		}
	},
	{
		'keys': ['@id', 'dbo:wikiPageID','dbo:wikiPageRevisionID'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [uri, wikiPageID, wikiPageRevisionID] = value_list;
			var wiki_link = 'https://en.wikipedia.org/?curid='+wikiPageID;
			var label = format_link(uri);
			return `«${label}»'s <b>Wikipedia page</b> is «${template_expand(wiki_link,label)}».`
		}
	},
//------------ AIX360 Knowledge Base ------------
	{ 
		'keys': ['owl:sameAs'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`A document <b>referring to</b> it is ${to_external_link(value,value)}`,
				x=>`The following documents <b>refer to</b> it`,
				x=>to_external_link(value,value),
			)
		}
	},
	{ 
		'keys': ['dc:language'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			return '';
		}
	},
	{ 
		'keys': ['foaf:isPrimaryTopicOf'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			return '';
		}
	},
	{ 
		'keys': ['my:algorithm_code'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`An <b>algorithm code</b> of it is ${to_external_link(value,value)}`,
				x=>`Some <b>algorithm codes</b> of It are`,
				x=>to_external_link(value,value),
			)
		}
	},
	{ 
		'keys': ['rdfs:label','my:field_of'],
		'keys_to_hide_as_child': ['rdfs:label','my:field_of'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [label,field] = value_list;
			return get_formatted_tuple_template(is_in_array, field, 
				x=>`The «${label}» is a ${linkify(prefixed_string_to_uri('my:feature'),'feature')} used to decide whether to give the loan, and it is a <b>field of</b> the ${linkify(prefixed_string_to_uri('my:sample'),'data samples')} of the «${x}»`, 
				x=>`The «${label}» is a ${linkify(prefixed_string_to_uri('my:feature'),'feature')} used to decide whether to give the loan, and it is a <b>field of</b> the ${linkify(prefixed_string_to_uri('my:sample'),'data samples')} of the following ${linkify(prefixed_string_to_uri('my:dataset'),'datasets')}`, 
			);
		}
	},
	{
		'keys': ['my:monotonicity_constraint'],
		// 'keys_to_hide_as_child': ['rdfs:field_of'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			if (value == prefixed_string_to_uri('my:monotonically_increasing'))
				return `The probability of getting the loan <b>increases</b> when the value of this feature <b>increases</b>.`;
			return `The probability of getting the loan <b>decreases</b> when the value of this feature <b>increases</b>.`;
		}
	},
	{
		'keys': ['rdfs:label', 'my:feature_order', 'my:value', 'my:counterfactual_api_url'],
		'optional_keys': ['rdfs:label'],
		'label': 'counterfactual',
		'hide_descendants': true,
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [label, feature_order, value, counterfactual_api_url] = value_list;
			var label_str = (label)?`your «${clip_text(label,25)}»`:'this feature';
			return `<div class="initial_explanans">The value of ${label_str} is <b>${value}</b>, but now you can change it to: ${counterfactual_input(counterfactual_api_url, feature_order, value)}.</div>`;
		},
	},
	{
		'keys': ['my:fields'],
		// 'keys_to_hide_as_child': ['rdfs:field_of'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`Every ${linkify(prefixed_string_to_uri('my:sample'),'data sample')} in this ${linkify(prefixed_string_to_uri('my:dataset'),'dataset')} has a <b>field</b> named «${x}»`, 
				x=>`Every ${linkify(prefixed_string_to_uri('my:sample'),'data sample')} in this ${linkify(prefixed_string_to_uri('my:dataset'),'dataset')} has the following <b>fields</b>`,
			)
		}
	},
	{
		'keys': ['my:field_of'],
		// 'keys_to_hide_as_child': ['rdfs:field_of'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value,
				x=>`This is a ${linkify(prefixed_string_to_uri('my:feature'),'feature')} used to decide whether to give the loan, and it is a <b>field of</b> the data samples of the «${x}».`, 
				x=>`This is a ${linkify(prefixed_string_to_uri('my:feature'),'feature')} used to decide whether to give the loan, and it is a <b>field of</b> the data samples of the following datasets`,  
			)
		}
	},
	{
		'keys': ['@type','my:kind_of'],
		'optional_keys': ['@type'],
		'keys_to_hide_as_child': ['@type','my:kind_of'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [type,value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`This is a <b>kind of</b> ${get_description(type)} «${x}»`, 
				x=>`This is a <b>kind of</b>`,
			)
		}
	},
	{
		'keys': ['my:algorithms'],
		'keys_to_hide_as_child': ['my:algorithms'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`An example of <b>algorithm</b> of this type is «${x}»`, 
				x=>`Some examples of <b>algorithms</b> of this type are`,
			)
		}
	},
	{
		'keys': ['my:understand'],
		// 'keys_to_hide_as_child': ['my:understand'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>x, 
				x=>`It is <b>used to understand</b>`,
			)
		}
	},
	{
		'keys': ['my:explanation_types'],
		// 'keys_to_hide_as_child': ['my:explanation_types'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`The <b>explanation</b> produced by It is a «${x}»`, 
				x=>`The <b>explanations</b> produced by It are`,
			)
		}
	},
	{
		'keys': ['my:feature'],
		// 'keys_to_hide_as_child': ['my:feature'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`It <b>is a feature</b> with id «${x}»`,
				x=>`It <b>is a feature</b> with ids`,
			)
		}
	},
	{ // 'reference'
		'keys': ['my:reference'],
		// 'keys_to_hide_as_child': ['my:reference'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`A document <b>referring to</b> It is ${linkify(value,value)}`,
				x=>`The following documents <b>refer to</b> It`,
			)
		}
	},
	{ 
		'keys': ['prov:wasDerivedFrom'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`It is <b>derived</b> from ${linkify(value,value)}.`,
				x=>`It is <b>derived</b> from`,
			)
		}
	},
	{ 
		'keys': ['dce:rights'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`A document <b>containing the rights</b> of It is ${linkify(value,value)}`,
				x=>`The following documents <b>contain the rights</b> of It`,
			)
		}
	},
	{ 
		'keys': ['foaf:thumbnail'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`A <b>thumbnail</b> of it is ${linkify(value,value)}`,
				x=>`It has the following <b>thumbnails</b>`,
			)
		}
	},
	{ 
		'keys': ['dbo:thumbnail'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`A <b>thumbnail</b> of it is ${linkify(value,value)}`,
				x=>`It has the following <b>thumbnails</b>`,
			)
		}
	},
	{ 
		'keys': ['foaf:depiction'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`An image <b>depicting</b> It is ${linkify(value,value)}`,
				x=>`The following images <b>depict</b> It`,
			)
		}
	},
//------------ YAI4Law ------------
	{ 
		'keys': ['my:url'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`You can find it here ${to_external_link(value,value)}`,
				x=>`You can find it here ${value.slice(0,1).map(y=>to_external_link(get_description(y),get_description(y))).join(', ')}, etc..`,
				x=>to_external_link(value,value),
			)
		}
	},
	{ 
		'keys': ['my:summary','my:sub_summary_list'],
		'keys_to_hide_as_child': ['my:summary','my:sub_summary_list'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>x,
				x=>`${x.slice(0,1).map(y=>to_external_link(get_description(y),get_description(y))).join(', ')}, etc..`,
			)
		}
	},
	// { 
	// 	'keys': ['my:sub_summary_list'],
	// 	'template_fn': (is_in_array, ancestor_predicate, value_list) => {
	// 		var [value] = value_list;
	// 		return get_formatted_tuple_template(is_in_array, value, 
	// 			x=>'',
	// 			x=>'',
	// 		)
	// 	}
	// },
	{
		'keys': ['my:content', 'my:docID', 'my:hasIDX', 'my:article_id', 'my:paragraph_id', 'my:block_id', 'my:section_id', 'my:chapter_id', 'my:reference_id'],
		'optional_keys': ['my:hasIDX', 'my:article_id', 'my:paragraph_id', 'my:block_id', 'my:section_id', 'my:chapter_id', 'my:reference_id'],
		'hide_descendants': true,
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [content,doc_url,label_idx,article_id,paragraph_id,block_id,section_id,chapter_id,reference_id] = value_list;
			var head_list = [];
			var value_list = [];
			// Get article
			var article = [];
			if (article_id)
				article.push(get_description(article_id));
			if (paragraph_id)
				article.push(get_description(paragraph_id));
			if (block_id)
				article.push(get_description(block_id));
			// Get section
			var section = [];
			if (chapter_id)
				section.push(get_description(chapter_id));
			if (section_id)
				section.push(get_description(section_id));
			// Populate table
			if (article.length > 0)
			{
				head_list.push('Article');
				value_list.push(article.map(x=>linkify(x,get_known_label(x))).join('.'));
			}
			if (section.length > 0)
			{
				head_list.push('Section');
				value_list.push(section.map(x=>linkify(x,get_known_label(x))).join('.'));
			}
			doc_url = get_description(doc_url, false);
			head_list = head_list.concat(['Source','Document']);
			value_list = value_list.concat([content,linkify(doc_url, get_known_label(doc_url))]);
			return get_table(head_list, [value_list]);
		}
	},
	{
		'keys': ['my:hasSource'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [value] = value_list;
			return get_formatted_tuple_template(is_in_array, value, 
				x=>`It has been found in 1 <b>source</b>`,
				x=>`It has been found in ${x.length} <b>sources</b>`,
				x=>'',
			)
		}
	},
	{ 
		'keys': ['my:triple','my:abstract','my:confidence','my:sentence','my:hasSource','my:source_id','my:syntactic_similarity','my:semantic_similarity'],
		'optional_keys': ['my:triple','my:abstract','my:hasSource','my:source_id','my:syntactic_similarity','my:semantic_similarity'],
		'hide_descendants': true,
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [triple,abstract,pertinence,sentence,source,source_id,syntactic_similarity,semantic_similarity] = value_list;
			const p = prefixed_string_to_uri;
			var head_list = ['Pertinence'];
			var value_list = [format_percentage(pertinence)];
			if (source)
			{
				// console.log(source, get_description(source[p('my:docID')], false));
				var doc_url = get_description(source[p('my:docID')], false);
				var article_id = get_description(source[p('my:article_id')]);
				var paragraph_id = get_description(source[p('my:paragraph_id')]);
				var block_id = get_description(source[p('my:block_id')]);
				var chapter_id = get_description(source[p('my:chapter_id')]);
				var section_id = get_description(source[p('my:section_id')]);
				// Get article
				var article = [];
				if (article_id)
					article.push(get_description(article_id));
				if (paragraph_id)
					article.push(get_description(paragraph_id));
				if (block_id)
					article.push(get_description(block_id));
				// Get section
				var section = [];
				if (chapter_id)
					section.push(get_description(chapter_id));
				if (section_id)
					section.push(get_description(section_id));
				// Populate table
				if (article.length > 0)
				{
					head_list.push('Article');
					value_list.push(article.map(x=>linkify(x,get_known_label(x))).join('.'));
				}
				if (section.length > 0)
				{
					head_list.push('Section');
					value_list.push(section.map(x=>linkify(x,get_known_label(x))).join('.'));
				}
				head_list = head_list.concat(['Source','Document']);
				value_list = value_list.concat([sentence,linkify(doc_url, get_known_label(doc_url))]);
			}
			else
			{
				head_list.push('Source');
				value_list.push(sentence);
			}
			return get_table(head_list, [value_list]);
		}
	},
	{
		'keys': ['my:answer_quality'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [quality_dict] = value_list;
			const p = prefixed_string_to_uri;
			const quality_percentage = get_description(quality_dict[p('my:semantic_similarity')])
			var quality_value = 'Unknown';
			if (quality_percentage < 0.3)
				quality_value = 'Bad';
			else if (quality_percentage < 0.5)
				quality_value = 'Not So Good';
			else if (quality_percentage < 0.7)
				quality_value = 'Sufficient';
			else
				quality_value = 'Good';
			return `The <b>quality</b> of this answer is estimated to be <b>${quality_value}</b>`;
		}
	},
	{
		'keys': ['my:valid_answers_count'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [valid_answer_count] = value_list;
			return `The answer has been obtained by combining <b>${valid_answer_count}</b> different <b>sources</b> of text`;
		}
	},
	{
		'keys': ['my:semantic_similarity'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [semantic_similarity] = value_list;
			return `The <b>semantic pertinence</b> is <b>${format_percentage(semantic_similarity)}</b>`;
		}
	},
	{
		'keys': ['my:syntactic_similarity'],
		'template_fn': (is_in_array, ancestor_predicate, value_list) => {
			var [syntactic_similarity] = value_list;
			return `The <b>syntactic pertinence</b> is <b>${format_percentage(syntactic_similarity)}</b>`;
		}
	},
];

// Remove duplicates from the template list
console.log('Template list size BEFORE unique elements filter:',TEMPLATE_LIST.length);
TEMPLATE_LIST = get_unique_elements(TEMPLATE_LIST, x => [...x.keys].sort().join('-'));
console.log('Template list size AFTER unique elements filter:',TEMPLATE_LIST.length);