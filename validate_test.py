import lxml.etree as etree

def validate_xml(xml_path, xsd_path):
    """Validate XML against XSD schema"""
    try:
        # Parse XML
        xml_doc = etree.parse(xml_path)
        
        # Parse XSD
        xsd_doc = etree.parse(xsd_path)
        schema = etree.XMLSchema(xsd_doc)
        
        # Validate
        is_valid = schema.validate(xml_doc)
        
        if not is_valid:
            print("XML validation errors:")
            for error in schema.error_log:
                print(f"Line {error.line}: {error.message}")
        else:
            print("XML is valid!")
        
        return is_valid
    except Exception as e:
        print(f"Error validating XML: {e}")
        return False

if __name__ == '__main__':
    validate_xml('test_doh_kdvp.xml', 'Doh_Kdvp_1_8.xsd') 