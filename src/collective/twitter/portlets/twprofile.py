# -*- coding: utf-8 -*-

from zope.interface import implements
from zope.interface import alsoProvides

from plone.portlets.interfaces import IPortletDataProvider
from plone.app.portlets.portlets import base

from zope import schema
from zope.component import getUtility

from zope.formlib import form
from zope.schema.vocabulary import SimpleVocabulary

from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from plone.registry.interfaces import IRegistry
from zope.schema.interfaces import IContextSourceBinder
from collective.prettydate.interfaces import IPrettyDate

from zope.security import checkPermission

from collective.twitter.portlets.config import PROJECTNAME

from collective.twitter.portlets import _

from collective.twitter.feed.interfaces import IFeedUtility

from plone.memoize import ram
from time import time

import DateTime
import twitter
import logging

logger = logging.getLogger(PROJECTNAME)


def TwitterAccounts(context):
    registry = getUtility(IRegistry)
    accounts = registry['collective.twitter.accounts']
    if accounts:
        vocab = accounts.keys()
    else:
        vocab = []

    return SimpleVocabulary.fromValues(vocab)


alsoProvides(TwitterAccounts, IContextSourceBinder)


def cache_key_simple(func, var):
    #let's memoize for 10 minutes or if any value of the portlet is modified
    timeout = time() // (60 * 10)
    return (timeout,
            var.data.tw_account,
            var.data.tw_user,
            var.data.max_results)


class ITwitterProfilePortlet(IPortletDataProvider):
    """A portlet

    It inherits from IPortletDataProvider because for this portlet, the
    data that is being rendered and the portlet assignment itself are the
    same.
    """

    header = schema.TextLine(title=_(u'Header'),
                                    description=_(u"The header for the portlet. Leave empty for none."),
                                    required=False)

    tw_account = schema.Choice(title=_(u'Twitter account'),
                               description=_(u"Which twitter account to use."),
                               required=True,
                               source=TwitterAccounts)

    tw_user = schema.TextLine(title=_(u'Twitter user'),
                              description=_(u"The Twitter user you wish to get feed from (you can include or omit the initial @)."),
                              required=True)

    show_avatars = schema.Bool(title=_(u'Show avatars'),
                               description=_(u"Show people's avatars."),
                               required=False)

    max_results = schema.Int(title=_(u'Maximum results'),
                               description=_(u"The maximum results number."),
                               required=True,
                               default=5)

    pretty_date = schema.Bool(title=_(u'Pretty dates'),
                              description=_(u"Show dates in a pretty format (ie. '4 hours ago')."),
                              default=True,
                              required=False)


class Assignment(base.Assignment):
    """Portlet assignment.

    This is what is actually managed through the portlets UI and associated
    with columns.
    """

    implements(ITwitterProfilePortlet)

    header = u""
    tw_account = u""
    tw_user = u""
    show_avatars = u""
    max_results = 20
    pretty_date = True

    def __init__(self,
                 tw_account,
                 tw_user,
                 max_results,
                 header=u"",
                 show_avatars=u"",
                 pretty_date=True):

        self.header = header
        self.tw_account = tw_account
        self.tw_user = tw_user
        self.show_avatars = show_avatars
        self.max_results = max_results
        self.pretty_date = pretty_date

    @property
    def title(self):
        """This property is used to give the title of the portlet in the
        "manage portlets" screen.
        """
        return _(u"Twitter profile Portlet")


class Renderer(base.Renderer):
    """Portlet renderer.

    This is registered in configure.zcml. The referenced page template is
    rendered, and the implicit variable 'view' will refer to an instance
    of this class. Other methods can be added and referenced in the template.
    """

    render = ViewPageTemplateFile('twprofile.pt')

    def getHeader(self):
        """
        Returns the header for the portlet
        """
        return self.data.header

    def canEdit(self):
        return checkPermission('cmf.ModifyPortalContent', self.context)

    def isValidAccount(self):
        registry = getUtility(IRegistry)
        accounts = registry.get('collective.twitter.accounts', [])

        return self.data.tw_account in accounts

    @ram.cache(cache_key_simple)
    def getSearchResults(self):
        logger.info("Getting tweets.")
        
        results = []

        if self.isValidAccount():
            logger.info("Got a valid account.")

            tw_user = self.data.tw_user
            max_results = self.data.max_results

            try:
                results = self.feed_tool.get_timeline(tw_user, count=max_results)
                logger.info("%s results obtained." % len(results))
            except Exception, e:
                logger.info("Something went wrong: %s." % e)
                results = []
        return results

    @property
    def feed_tool(self):
        util = getUtility(IFeedUtility, name="timeline")
        return util(self.data.tw_account,
                    request=self.request,
                    context=self.context)

class AddForm(base.AddForm):
    """Portlet add form.

    This is registered in configure.zcml. The form_fields variable tells
    zope.formlib which fields to display. The create() method actually
    constructs the assignment that is being added.
    """
    form_fields = form.Fields(ITwitterProfilePortlet)

    def create(self, data):
        return Assignment(**data)


class EditForm(base.EditForm):
    """Portlet edit form.

    This is registered with configure.zcml. The form_fields variable tells
    zope.formlib which fields to display.
    """
    form_fields = form.Fields(ITwitterProfilePortlet)
