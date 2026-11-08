from pydantic import ValidationError
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location("quickbite_delivery_testmod", Path(__file__).parents[1]/"main.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DeliveryRequest=module.DeliveryRequest

def test_valid_delivery():
    d=DeliveryRequest(orderId=' 00000000-0000-0000-0000-000000000001 ',customerAddress='  18 Example Road ')
    assert d.customerAddress=='18 Example Road'

def test_empty_address_rejected():
    try:DeliveryRequest(orderId='00000000-0000-0000-0000-000000000001',customerAddress='  ')
    except ValidationError:return
    raise AssertionError('Expected address validation')
