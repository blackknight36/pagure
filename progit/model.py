#-*- coding: utf-8 -*-

"""
 (c) 2014 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>

"""

__requires__ = ['SQLAlchemy >= 0.8', 'jinja2 >= 2.4']
import pkg_resources

import datetime
import logging

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import relation

BASE = declarative_base()

ERROR_LOG = logging.getLogger('progit.model')


def create_tables(db_url, alembic_ini=None, debug=False):
    """ Create the tables in the database using the information from the
    url obtained.

    :arg db_url, URL used to connect to the database. The URL contains
        information with regards to the database engine, the host to
        connect to, the user and password and the database name.
          ie: <engine>://<user>:<password>@<host>/<dbname>
    :kwarg alembic_ini, path to the alembic ini file. This is necessary
        to be able to use alembic correctly, but not for the unit-tests.
    :kwarg debug, a boolean specifying wether we should have the verbose
        output of sqlalchemy or not.
    :return a session that can be used to query the database.

    """
    engine = create_engine(db_url, echo=debug)
    from progit.ui.plugins import get_plugin_tables
    get_plugin_tables()
    BASE.metadata.create_all(engine)
    #engine.execute(collection_package_create_view(driver=engine.driver))
    if db_url.startswith('sqlite:'):
        ## Ignore the warning about con_record
        # pylint: disable=W0613
        def _fk_pragma_on_connect(dbapi_con, con_record):
            ''' Tries to enforce referential constraints on sqlite. '''
            dbapi_con.execute('pragma foreign_keys=ON')
        sa.event.listen(engine, 'connect', _fk_pragma_on_connect)

    if alembic_ini is not None:  # pragma: no cover
        # then, load the Alembic configuration and generate the
        # version table, "stamping" it with the most recent rev:

        ## Ignore the warning missing alembic
        # pylint: disable=F0401
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config(alembic_ini)
        command.stamp(alembic_cfg, "head")

    scopedsession = scoped_session(sessionmaker(bind=engine))
    # Insert the default data into the db
    try:
        create_default_status(scopedsession)
    except SQLAlchemyError:
        pass
    return scopedsession


def create_default_status(session):
    """ Insert the defaults status in the status tables.
    """

    for status in ['Open', 'Invalid', 'Insufficient data', 'Fixed']:
        ticket_stat = StatusIssue(status=status)
        session.add(ticket_stat)
        try:
            session.flush()
        except SQLAlchemyError, err:
            ERROR_LOG.debug('Status %s could not be added', ticket_stat)

    session.commit()


class StatusIssue(BASE):
    """ Stores the status a ticket can have.

    Table -- status_issue
    """
    __tablename__ = 'status_issue'

    id = sa.Column(sa.Integer, primary_key=True)
    status = sa.Column(sa.Text, nullable=False, unique=True)


class User(BASE):
    """ Stores information about users.

    Table -- users
    """

    __tablename__ = 'users'
    id = sa.Column(sa.Integer, primary_key=True)
    user = sa.Column(sa.String(32), nullable=False, unique=True, index=True)
    fullname = sa.Column(sa.Text, nullable=False, index=True)
    public_ssh_key = sa.Column(sa.Text, nullable=True)

    password = sa.Column(sa.Text, nullable=True)
    token = sa.Column(sa.String(50), nullable=True)
    created = sa.Column(
        sa.DateTime,
        nullable=False,
        default=sa.func.now())
    updated_on = sa.Column(
        sa.DateTime,
        nullable=False,
        default=sa.func.now(),
        onupdate=sa.func.now())

    # Relations
    group_objs = relation(
        "ProgitGroup",
        secondary="progit_user_group",
        primaryjoin="users.c.id==progit_user_group.c.user_id",
        secondaryjoin="progit_group.c.id==progit_user_group.c.group_id",
        backref="users",
    )
    session = relation("ProgitUserVisit", backref="user")

    @property
    def username(self):
        ''' Return the username. '''
        return self.user

    @property
    def groups(self):
        ''' Return the list of Group.group_name in which the user is. '''
        return [group.group_name for group in self.group_objs]

    def __repr__(self):
        ''' Return a string representation of this object. '''

        return 'User: %s - name %s' % (self.id, self.user)


class UserEmail(BASE):
    """ Stores email information about the users.

    Table -- user_emails
    """

    __tablename__ = 'user_emails'
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('users.id', onupdate='CASCADE'),
        nullable=False,
        index=True)
    email = sa.Column(sa.Text, nullable=False, unique=True)

    user = relation('User', foreign_keys=[user_id],
                    remote_side=[User.id], backref='emails')


class Project(BASE):
    """ Stores the projects.

    Table -- projects
    """

    __tablename__ = 'projects'

    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('users.id', onupdate='CASCADE'),
        nullable=False,
        index=True)
    name = sa.Column(sa.String(32), nullable=False, index=True)
    description = sa.Column(sa.Text, nullable=True)
    parent_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('projects.id', onupdate='CASCADE'),
        nullable=True)
    issue_tracker = sa.Column(sa.Boolean, nullable=False, default=True)
    project_docs = sa.Column(sa.Boolean, nullable=False, default=True)

    date_created = sa.Column(sa.DateTime, nullable=False,
                             default=datetime.datetime.utcnow)

    parent = relation('Project', remote_side=[id], backref='forks')
    user = relation('User', foreign_keys=[user_id],
                    remote_side=[User.id], backref='projects')

    @property
    def path(self):
        ''' Return the name of the git repo on the filesystem. '''
        if self.parent_id:
            path = '%s/%s.git' % (self.user.user, self.name)
        else:
            path = '%s.git' % (self.name)
        return path

    @property
    def is_fork(self):
        ''' Return a boolean specifying if the project is a fork or not '''
        return self.parent_id is not None

    @property
    def fullname(self):
        ''' Return the name of the git repo as user/project if it is a
        project forked, otherwise it returns the project name.
        '''
        str_name = self.name
        if self.parent_id:
            str_name = "%s/%s" % (self.user.user, str_name)
        return str_name


class ProjectUser(BASE):
    """ Stores the user of a projects.

    Table -- user_projects
    """

    __tablename__ = 'user_projects'
    __table_args__ = (
        sa.UniqueConstraint('project_id', 'user_id'),
    )

    id = sa.Column(sa.Integer, primary_key=True)
    project_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('projects.id', onupdate='CASCADE'),
        nullable=False)
    user_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('users.id', onupdate='CASCADE'),
        nullable=False,
        index=True)

    project = relation(
        'Project', foreign_keys=[project_id], remote_side=[Project.id],
        backref='users')
    user = relation('User', foreign_keys=[user_id],
                    remote_side=[User.id], backref='co_projects')


class Issue(BASE):
    """ Stores the issues reported on a project.

    Table -- issues
    """

    __tablename__ = 'issues'

    id = sa.Column(sa.Integer, primary_key=True)
    uid = sa.Column(sa.String(32), unique=True)
    project_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            'projects.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False)
    title = sa.Column(
        sa.Text,
        nullable=False)
    content = sa.Column(
        sa.Text(),
        nullable=False)
    user_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('users.id', onupdate='CASCADE'),
        nullable=False,
        index=True)
    status = sa.Column(
        sa.Text,
        sa.ForeignKey(
            'status_issue.status', ondelete='CASCADE', onupdate='CASCADE'),
        default='Open',
        nullable=False)

    date_created = sa.Column(sa.DateTime, nullable=False,
                             default=datetime.datetime.utcnow)

    project = relation(
        'Project', foreign_keys=[project_id], remote_side=[Project.id],
        backref='issues')
    user = relation('User', foreign_keys=[user_id],
                    remote_side=[User.id], backref='issues')

    def __repr__(self):
        return 'Issue(%s, project:%s, user:%s, title:%s)' % (
            self.id, self.project.name, self.user.user, self.title
        )

    @property
    def mail_id(self):
        ''' Return a unique reprensetation of the issue as string that
        can be used when sending emails.
        '''
        return '%s-ticket-%s@progit' % (self.project.name, self.id)


class IssueComment(BASE):
    """ Stores the comments made on a commit/file.

    Table -- issue_comments
    """

    __tablename__ = 'issue_comments'

    id = sa.Column(sa.Integer, primary_key=True)
    issue_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            'issues.id', ondelete='CASCADE', onupdate='CASCADE'),
        index=True)
    comment = sa.Column(
        sa.Text(),
        nullable=False)
    parent_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('issue_comments.id', onupdate='CASCADE'),
        nullable=True)
    user_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('users.id', onupdate='CASCADE'),
        nullable=False,
        index=True)

    date_created = sa.Column(sa.DateTime, nullable=False,
                             default=datetime.datetime.utcnow)

    issue = relation(
        'Issue', foreign_keys=[issue_id], remote_side=[Issue.id],
        backref='comments')
    user = relation('User', foreign_keys=[user_id],
                    remote_side=[User.id], backref='comment_issues')


class PullRequest(BASE):
    """ Stores the pull requests created on a project.

    Table -- pull_requests
    """

    __tablename__ = 'pull_requests'

    id = sa.Column(sa.Integer, primary_key=True)
    project_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            'projects.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False)
    project_id_from = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            'projects.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False)
    title = sa.Column(
        sa.Text,
        nullable=False)
    branch = sa.Column(
        sa.Text(),
        nullable=False)
    start_id = sa.Column(
        sa.String(40),
        nullable=True)
    stop_id = sa.Column(
        sa.String(40),
        nullable=False)
    user_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('users.id', onupdate='CASCADE'),
        nullable=False,
        index=True)
    status = sa.Column(sa.Boolean, nullable=False, default=True)

    date_created = sa.Column(sa.DateTime, nullable=False,
                             default=datetime.datetime.utcnow)

    repo = relation(
        'Project', foreign_keys=[project_id], remote_side=[Project.id],
        backref='requests')
    repo_from = relation(
        'Project', foreign_keys=[project_id_from], remote_side=[Project.id])
    user = relation('User', foreign_keys=[user_id],
                    remote_side=[User.id], backref='pull_requests')

    def __repr__(self):
        return 'PullRequest(%s, project:%s, user:%s, title:%s)' % (
            self.id, self.repo.name, self.user.user, self.title
        )

    @property
    def mail_id(self):
        ''' Return a unique reprensetation of the issue as string that
        can be used when sending emails.
        '''
        return '%s-pull-request-%s@progit' % (self.repo.name, self.id)


class PullRequestComment(BASE):
    """ Stores the comments made on a pull-request.

    Table -- pull_request_comments
    """

    __tablename__ = 'pull_request_comments'

    id = sa.Column(sa.Integer, primary_key=True)
    pull_request_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            'pull_requests.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False)
    commit_id = sa.Column(
        sa.String(40),
        nullable=False,
        index=True)
    user_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('users.id', onupdate='CASCADE'),
        nullable=False,
        index=True)
    line = sa.Column(
        sa.Integer,
        nullable=True)
    comment = sa.Column(
        sa.Text(),
        nullable=False)
    parent_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('pull_request_comments.id', onupdate='CASCADE'),
        nullable=True)

    date_created = sa.Column(sa.DateTime, nullable=False,
                             default=datetime.datetime.utcnow)

    user = relation('User', foreign_keys=[user_id],
                    remote_side=[User.id], backref='pull_request_comments')
    pull_request = relation(
        'PullRequest', foreign_keys=[pull_request_id], remote_side=[PullRequest.id],
        backref='comments')


class GlobalId(BASE):
    """ Store the mapping of the project with their issue and pull-request
    and provides us with a way to get global identifier per project

    Table -- global_id
    """

    __tablename__ = 'global_id'

    id = sa.Column(sa.Integer, primary_key=True)
    project_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            'projects.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False)
    issue_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            'issues.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=True)
    request_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            'pull_requests.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=True)

    project = relation(
        'Project', foreign_keys=[project_id], remote_side=[Project.id],
        backref='global_id')
    issue = relation(
        'Issue', foreign_keys=[issue_id], remote_side=[Issue.id],
        backref='global_id')
    request = relation(
        'PullRequest', foreign_keys=[request_id], remote_side=[PullRequest.id],
        backref='global_id')

    __table_args__ = (
        # Both fields should not be NULL
        sa.CheckConstraint('NOT(request_id IS NULL AND issue_id IS NULL)'),
        # Both fields should not be not NULL (ie: only one of them should)
        sa.CheckConstraint('NOT(request_id IS NOT NULL AND issue_id IS NOT NULL)'),
    )


# ##########################################################
# These classes are only used if you're using the `local`
#                  authentication method
# ##########################################################


class ProgitUserVisit(BASE):

    __tablename__ = 'progit_user_visit'

    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(
        sa.Integer, sa.ForeignKey('users.id'), nullable=False)
    visit_key = sa.Column(
        sa.String(40), nullable=False, unique=True, index=True)
    user_ip = sa.Column(sa.String(50), nullable=False)
    created = sa.Column(
        sa.DateTime, nullable=False, default=datetime.datetime.utcnow)
    expiry = sa.Column(sa.DateTime)


class ProgitGroup(BASE):
    """
    An ultra-simple group definition.
    """

    # names like "Group", "Order" and "User" are reserved words in SQL
    # so we set the name to something safe for SQL
    __tablename__ = 'progit_group'

    id = sa.Column(sa.Integer, primary_key=True)
    group_name = sa.Column(sa.String(16), nullable=False, unique=True)
    created = sa.Column(
        sa.DateTime, nullable=False, default=datetime.datetime.utcnow)

    def __repr__(self):
        ''' Return a string representation of this object. '''

        return 'Group: %s - name %s' % (self.id, self.group_name)


class ProgitUserGroup(BASE):
    """
    Association table linking the mm_user table to the mm_group table.
    This allow linking users to groups.
    """

    __tablename__ = 'progit_user_group'

    user_id = sa.Column(
        sa.Integer, sa.ForeignKey('users.id'), primary_key=True)
    group_id = sa.Column(
        sa.Integer, sa.ForeignKey('progit_group.id'), primary_key=True)

    # Constraints
    __table_args__ = (
        sa.UniqueConstraint(
            'user_id', 'group_id'),
    )
