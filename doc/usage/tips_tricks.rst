Tips and tricks
===============

This page contains some tips and tricks on how to use pagure. These do not
fit in their own page but are worth mentioning.


Pre-fill issue template using the URL
-------------------------------------

When Creating Issues for a project , Pagure supports pre-filling the title
and description input text using url parameters

Example:
~~~~~~~~
https://pagure.io/pagure/new_issue/?title=<Issue>&content=<Issue Content>

The above URL will autofill the text boxes for Title and Description field
with Title set to <Issue> and Description set to <Issue Content>.


Filter for issues *not* having a certain tag
--------------------------------------------

Very much in the same way pagure allows you to filter for issues having a
certain tag, pagure allows to filter for issues *not* having a certain tag.
To do this, simply prepend a ``!`` in front of the tag.

Example:
~~~~~~~~
https://pagure.io/pagure/issues?tags=!easyfix