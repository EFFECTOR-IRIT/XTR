from rdflib import OWL, RDF, RDFS, Literal
from xsd_to_rdf.entity.entity import Entity
from xsd_to_rdf.entity.object_property import ObjectProperty
from xsd_to_rdf.entity.data_property import DataProperty
from xsd_to_rdf.settings import settings


# TODO: no global 
PARENT_TAG = settings.get('xsd_nodes').get('common').get('parent_tag',)
SEQUENCE_TAG = settings.get('xsd_nodes').get('common').get('sequence_tag')
ELEMENT_TAG = settings.get('xsd_nodes').get('common').get('element_tag')
RESTRICTION_TAG = settings.get('xsd_nodes').get('common').get('restriction_tag')
MIN_VALUE_TAG = settings.get('xsd_nodes').get('common').get('min_value_tag')
MAX_VALUE_TAG = settings.get('xsd_nodes').get('common').get('max_value_tag')
EXCLUDED_PARENTS = settings.get('xsd_nodes').get('thing_class').get('excluded_parents')
XSD_TYPES = settings.get('xsd_types')


class ThingClass(Entity):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.type = OWL.Class

    # TODO: rework thing_class converter
    def convert_to_rdf(self):
        super().convert_to_rdf()
        self.set_type()
        self.set_super_element()
        sequence = next((
            item for item in self.node.getiterator()
            if SEQUENCE_TAG in item.tag),
            None)
        for element in sequence:
            entity = None
            restriction = next((
                item for item in element.getiterator()
                if RESTRICTION_TAG in item.tag),
                None)
            # TODO: rework options build
            parameters = dict(
                graph = self.graph,
                name = element.attrib.get('name'),
                namespace = self.namespace,
                node = element,
                options = self.options,
                associated_class = self,
                domain = self
            )
            # TODO: rework dataproperty
            if element.attrib.get('type') in XSD_TYPES.values():
                parameters.update(dict(xsd_type = element.attrib.get('type')))
                entity = DataProperty(**parameters)
            elif restriction is not None:
                min_value = next((
                    item for item in restriction.getiterator()
                    if MIN_VALUE_TAG in item.tag),
                    None)
                max_value = next((
                    item for item in restriction.getiterator()
                    if MAX_VALUE_TAG in item.tag),
                    None)
                parameters.update(dict(
                    xsd_type = restriction.attrib.get('base'),
                    min_value = min_value.attrib.get('value'),
                    max_value = max_value.attrib.get('value'))
                )
                entity = DataProperty(**parameters)
            elif element.attrib.get('type') is None and \
                restriction is None:
                element_sequence = next((
                    item for item in element.getiterator()
                    if SEQUENCE_TAG in item.tag),
                    None)
                if len(element_sequence) == 0 and restriction is None:
                    raise ValueError(element.attrib.get('name'))
                if len(element_sequence) == 1:
                    [range] = element_sequence
                    parameters.update(dict(
                        range = range.attrib.get('type'))
                    )

                    entity = ObjectProperty(**parameters)
                else:
                    entity = RelationshipClass(**parameters)
            else:
                parameters.update(dict(
                    range = element.attrib.get('type'))
                )
                entity = ObjectProperty(**parameters)
            entity.convert_to_rdf()
            self.sub_elements.append(entity)

    def set_super_element(self):
        parent = next((
            elem for elem in self.node.getiterator()
            if PARENT_TAG in elem.tag),
            None)
        if parent is None: return
        if parent.attrib.get('base') in EXCLUDED_PARENTS: return
        base = parent.attrib.get('base')
        base_ns = base[:base.index(':')]
        base_entity = base[base.index(':') + 1:]
        namespace = next((
            value for (key, value) in self.node.nsmap.items()
            if key == base_ns))
        self.super_entity = ThingClass(
            graph = self.graph,
            name = base_entity,
            namespace = namespace
        )
        super_class_uri = self.super_entity.get_namespace[self.super_entity.get_name]
        self.graph.add_triplet((self.uri, RDFS.subClassOf, super_class_uri))
        self.graph.add_triplet((
            super_class_uri,
            RDFS.label,
            Literal(self.super_entity.get_name))
        )


class RelationshipClass(ThingClass):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.type = OWL.Class
        self.associated_class = kwargs.get('associated_class')

    def convert_to_rdf(self):
        super().convert_to_rdf()
        self.set_association()

    def set_super_element(self):
        default_super_class = next((
            cls for cls in self.options.get('super_classes')
            if cls.get('super_class_of') == __class__.__name__),
            None)
        if default_super_class is None: return
        self.super_entity = Entity(
            graph = self.graph,
            name = default_super_class.get('label'),
            namespace = default_super_class.get('namespace'))
        super_class_uri = self.super_entity.namespace[self.super_entity.get_name]
        self.graph.add_triplet((self.uri, RDFS.subClassOf, super_class_uri))
        self.graph.add_triplet((
            super_class_uri,
            RDFS.label,
            Literal(self.super_entity.get_name))
        )
        self.graph.bind_namespace(
            self.super_entity.get_prefix, self.super_entity.get_namespace)

    def set_association(self):
        association = ObjectProperty(
            graph = self.graph,
            name = self.associated_class.get_name,
            namespace = self.namespace,
            node = self.node,
            options = self.options,
            domain = self,
            range = (self.prefix + ':' + self.associated_class.get_name)
        )
        association.convert_to_rdf()

    def set_name_with_convention(self):
        self.name = self.associated_class.get_name + self.name
