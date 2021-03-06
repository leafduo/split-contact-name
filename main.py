from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app, login_required
from google.appengine.api import users
import gdata.gauth
import gdata.contacts.client

from config import *

# Constants included for ease of understanding. It is a more common
# and reliable practice to create a helper for reading a Consumer Key
# and Secret from a config file. You may have different consumer keys
# and secrets for different environments, and you also may not want to
# check these values into your source code repository.

# Create an instance of the DocsService to make API calls
gc = gdata.contacts.client.ContactsClient(source = SETTINGS['APP_NAME'])

class Fetcher(webapp.RequestHandler):

    @login_required
    def get(self):
        """This handler is responsible for fetching an initial OAuth
        request token and redirecting the user to the approval page."""

        current_user = users.get_current_user()

        # We need to first get a unique token for the user to
        # promote.
        #
        # We provide the callback URL. This is where we want the
        # user to be sent after they have granted us
        # access. Sometimes, developers generate different URLs
        # based on the environment. You want to set this value to
        # "http://localhost:8080/step2" if you are running the
        # development server locally.
        #
        # We also provide the data scope(s). In general, we want
        # to limit the scope as much as possible. For this
        # example, we just ask for access to all feeds.
        scopes = 'https://www.google.com/m8/feeds/'
        oauth_callback = 'http://%s/step2' % self.request.host
        consumer_key = SETTINGS['CONSUMER_KEY']
        consumer_secret = SETTINGS['CONSUMER_SECRET']
        request_token = gc.get_oauth_token(scopes, oauth_callback,
                                              consumer_key, consumer_secret)

        # Persist this token in the datastore.
        request_token_key = 'request_token_%s' % current_user.user_id()
        gdata.gauth.ae_save(request_token, request_token_key)

        # Generate the authorization URL.
        approval_page_url = request_token.generate_authorization_url()

        message = """<a href="%s">
Request token for the Google Documents Scope</a>"""
        self.response.out.write(message % approval_page_url)


class RequestTokenCallback(webapp.RequestHandler):

    @login_required
    def get(self):
        """When the user grants access, they are redirected back to this
        handler where their authorized request token is exchanged for a
        long-lived access token."""

        current_user = users.get_current_user()

        # Remember the token that we stashed? Let's get it back from
        # datastore now and adds information to allow it to become an
        # access token.
        request_token_key = 'request_token_%s' % current_user.user_id()
        request_token = gdata.gauth.ae_load(request_token_key)
        gdata.gauth.authorize_request_token(request_token, self.request.uri)

        # We can now upgrade our authorized token to a long-lived
        # access token by associating it with gc client, and
        # calling the get_access_token method.
        gc.auth_token = gc.get_access_token(request_token)

        # Note that we want to keep the access token around, as it
        # will be valid for all API calls in the future until a user
        # revokes our access. For example, it could be populated later
        # from reading from the datastore or some other persistence
        # mechanism.
        access_token_key = 'access_token_%s' % current_user.user_id()
        gdata.gauth.ae_save(request_token, access_token_key)

        # Finally fetch the document list and print document title in
        # the response
        feed = gc.get_contacts()
        for entry in feed.entry:
            try:
                self.response.out.write(entry.name.full_name.text)
            except:
                pass


def main():
    application = webapp.WSGIApplication([('/step1', Fetcher),
                                          ('/step2', RequestTokenCallback)],
                                         debug=True)
    run_wsgi_app(application)

