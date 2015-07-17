from __future__ import absolute_import, unicode_literals

from datetime import datetime
import logging

from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render_to_response
from django.template import RequestContext
from django.utils.translation import ugettext_lazy as _

from common.utils import encapsulate
from permissions import Permission

from .api import Key
from .forms import KeySearchForm
from .permissions import (
    permission_key_delete, permission_key_receive, permission_key_view,
    permission_keyserver_query
)
from .runtime import gpg

logger = logging.getLogger(__name__)


def key_receive(request, key_id):
    Permission.check_permissions(request.user, [permission_key_receive])

    previous = request.POST.get('previous', request.GET.get('previous', request.META.get('HTTP_REFERER', reverse(settings.LOGIN_REDIRECT_URL))))

    if request.method == 'POST':
        try:
            gpg.receive_key(key_id=key_id)
        except Exception as exception:
            messages.error(
                request,
                _('Unable to import key: %(key_id)s; %(error)s') %
                {
                    'key_id': key_id,
                    'error': exception,
                }
            )
            return HttpResponseRedirect(previous)
        else:
            messages.success(
                request,
                _('Successfully received key: %(key_id)s') %
                {
                    'key_id': key_id,
                }
            )

            return redirect('django_gpg:key_public_list')

    return render_to_response('appearance/generic_confirm.html', {
        'title': _('Import key'),
        'message': _('Import key ID: %s?') % key_id,
        'previous': previous,
        'submit_method': 'GET',

    }, context_instance=RequestContext(request))


def key_list(request, secret=True):
    Permission.check_permissions(request.user, [permission_key_view])

    if secret:
        object_list = Key.get_all(gpg, secret=True)
        title = _('Private keys')
    else:
        object_list = Key.get_all(gpg)
        title = _('Public keys')

    return render_to_response('appearance/generic_list.html', {
        'object_list': object_list,
        'title': title,
        'hide_object': True,
        'extra_columns': [
            {
                'name': _('Key ID'),
                'attribute': 'key_id',
            },
            {
                'name': _('Owner'),
                'attribute': encapsulate(lambda x: ', '.join(x.uids)),
            },
        ]
    }, context_instance=RequestContext(request))


def key_delete(request, fingerprint, key_type):
    Permission.check_permissions(request.user, [permission_key_delete])

    secret = key_type == 'sec'
    key = Key.get(gpg, fingerprint, secret=secret)

    post_action_redirect = None
    previous = request.POST.get('previous', request.GET.get('previous', request.META.get('HTTP_REFERER', reverse(settings.LOGIN_REDIRECT_URL))))
    next = request.POST.get('next', request.GET.get('next', post_action_redirect if post_action_redirect else request.META.get('HTTP_REFERER', reverse(settings.LOGIN_REDIRECT_URL))))

    if request.method == 'POST':
        try:
            gpg.delete_key(key)
            messages.success(request, _('Key: %s, deleted successfully.') % fingerprint)
            return HttpResponseRedirect(next)
        except Exception as exception:
            messages.error(request, exception)
            return HttpResponseRedirect(previous)

    return render_to_response('appearance/generic_confirm.html', {
        'title': _('Delete key'),
        'delete_view': True,
        'message': _('Delete key %s? If you delete a public key that is part of a public/private pair the private key will be deleted as well.') % key,
        'next': next,
        'previous': previous,
    }, context_instance=RequestContext(request))


def key_query(request):
    Permission.check_permissions(request.user, [permission_keyserver_query])

    subtemplates_list = []
    term = request.GET.get('term')

    form = KeySearchForm(initial={'term': term})
    subtemplates_list.append(
        {
            'name': 'appearance/generic_form_subtemplate.html',
            'context': {
                'title': _('Query key server'),
                'form': form,
                'submit_method': 'GET',
            },
        }
    )

    if term:
        results = gpg.query(term)
        subtemplates_list.append(
            {
                'name': 'appearance/generic_list_subtemplate.html',
                'context': {
                    'title': _('results'),
                    'object_list': results,
                    'hide_object': True,
                    'extra_columns': [
                        {
                            'name': _('ID'),
                            'attribute': encapsulate(lambda item: '...{0}'.format(item.key_id[-16:])),
                        },
                        {
                            'name': _('Type'),
                            'attribute': 'key_type',
                        },
                        {
                            'name': _('Creation date'),
                            'attribute': encapsulate(lambda x: datetime.fromtimestamp(int(x.date)))
                        },
                        {
                            'name': _('Expiration date'),
                            'attribute': encapsulate(lambda x: datetime.fromtimestamp(int(x.expires)) if x.expires else _('No expiration'))
                        },
                        {
                            'name': _('Length'),
                            'attribute': 'length',
                        },
                        {
                            'name': _('Identities'),
                            'attribute': encapsulate(lambda x: ', '.join(x.uids)),
                        },
                    ]
                },
            }
        )

    return render_to_response('appearance/generic_form.html', {
        'subtemplates_list': subtemplates_list,
    }, context_instance=RequestContext(request))
