import abc

from aiohttp.web_request import Request
from aiohttp.web_urldispatcher import View


class BasePermission(metaclass=abc.ABCMeta):
    """
    A base class from which all permission classes should inherit.
    """

    @abc.abstractmethod
    def has_permission(self, request: Request, view: View):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        raise NotImplementedError()


class IsAuthenticatedForObject(BasePermission):
    """
    Allows access only to authenticated users with the same identifier as the resource identifier.
    """

    def has_permission(self, request: Request, view: View) -> bool:
        """
        Return `True` if permission is granted or `user.is_admin == True`, `False` otherwise.
        """
        return (request['payload'].get('id') == view.object_id) or request['payload'].get('is_admin', False)
