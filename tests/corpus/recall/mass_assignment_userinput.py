"""Recall fixture: mass assignment of user-controlled data into a model.

The dangerous call unpacks request data (an Attribute, request.data) straight
into a model constructor — the real vulnerability. The old detector only handled
a bare Name (**request_data) and missed the attribute form.
"""


class Order:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def create_order(request):
    return Order(**request.data)  # EXPECT: MassAssignment
