class RoxywiGroupMismatch(Exception):
    """ Raised when not superAdmin tris update resource not from its group. """

    def __init__(self):
        super(RoxywiGroupMismatch, self).__init__('Group ID does not match')


class RoxywiResourceNotFound(Exception):
    """ This class represents an exception raised when a resource is not found. """

    def __init__(self):
        super(RoxywiResourceNotFound, self).__init__('Resource not found')
