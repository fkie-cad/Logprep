===========
Development
===========

.. mermaid::

    classDiagram
        Component <-- Processor
        Component <-- Connector
        Connector <-- Input : implements
        Connector <-- Output : implements
        Processor <-- Normalizer : implements
        Processor <-- Pseudonymizer : implements
        Input <-- ConfluentKafkaInput : implements
        Output <-- ConfluentKafkaOutput : implements
        ProcessorConfiguration
        Rule <-- NormalizerRule : inherit
        Rule <-- PseudonymizerRule : inherit
        BaseProcessorTestCase <-- NormalizerTestCase : implements
        BaseProcessorTestCase <-- PseudonymizerTestCase : implements
        class Component{
            +Config
            +str name
            +Logger _logger
            +Config _config
            +String describe()
            +None setup()
            +None shut_down()
            
        }
        class Processor{
            <<interface>>
            +rule_class
            +Config
            +add_rules_from_directories()
            +process()
            +apply_rules()*
        }
        class Normalizer{
            +Config
            +rule_class = NormalizerRule
            +_config: Normalizer.Config
            +apply_rules()
        }

        class Pseudonymizer{
            +Config
            +rule_class = PseudonymizerRule
            +_config: Pseudonymizer.Config
            +apply_rules()
        }
        class Connector{
            <<interface>>
            +Config
        }
        class Input{
            <<interface>>
            +Config
            +_config: Input.Config
            -Dict _get_event()*
            -None _get_raw_event()
            +tuple[dict, error|None] get_next()
        }
        class Output{
            <<interface>>
            +Config
            +_config: Output.Config
            +None store()*
            +None store_custom()*
            +None store_failed()*
        }
        class ConfluentKafkaInput{
            +Config
            +_config: ConfluentKafkaInput.Config
            +tuple _get_event()
            +bytearray _get_raw_event()
        }
        class ConfluentKafkaOutput{
            +Config
            +_config: ConfluentKafkaInput.Config
            +None store()
            +None store_custom()
            +None store_failed()
        }

        class Configuration{
            <<adapter>>
            +create
        }
        class Registry{
            +mapping : dict
        }

        class Factory{
            +create()
        }


        class TestFactory{
            +test_check()
            +test_create_normalizer()
            +test_create_pseudonymizer()
        }

        class BaseProcessorTestCase{
            +test_describe()
            +test_add_rules_from_diretories()
            +test_process()
            +test_apply_rules()*
        }

        class NormalizerTestCase{
            +test_apply_rules()
        }

        class PseudonymizerTestCase{
            +test_apply_rules()
        }


.. toctree::
   :maxdepth: 2

   connector_how_to
   processor_how_to
   register_a_new_component
   requirements
   testing
