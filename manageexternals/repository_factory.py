from .repository_git import GitRepository
from .repository_svn import SvnRepository
from .model_description import ModelDescription
from .utils import fatal_error


def create_repository(component_name, repo_info):
    """Determine what type of repository we have, i.e. git or svn, and
    create the appropriate object.

    """
    protocol = repo_info[ModelDescription.PROTOCOL].lower()
    if protocol == 'git':
        repo = GitRepository(component_name, repo_info)
    elif protocol == 'svn':
        repo = SvnRepository(component_name, repo_info)
    elif protocol == 'externals_only':
        repo = None
    else:
        msg = 'Unknown repo protocol "{0}"'.format(protocol)
        fatal_error(msg)
    return repo
