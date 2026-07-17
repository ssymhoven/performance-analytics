<p align="center">
    <img src="https://www.donner-reuschel.lu/wp-content/uploads/2019/10/Donner-Reuschel-Logo-1-300x115.png">
</p>

# Table of contents

1. [How to use this template](#how-to-use-this-template)
2. [Provided Workflows](#provided-workflows) 
   1. [CI](#ci) (Continuous Integration)
   2. [Publish Docs](#publish-docs)
   3. [Sync labels](#sync-labels)
   4. [Release Drafter](#release-drafter)
   5. [Enforce Labels](#enforce-labels)
   6. [Dependabot](#dependabot)
3. [How to include your project as dependency in other projects](#how-to-include-your-project-as-dependency-in-other-projects)
4. [Prerequisites](#prerequisites)
    1. [Rename `project-name`](#rename-projectname)
    2. [Activate GitHub Pages to enable documentation](#activate-github-pages-to-enable-documentation)
    3. [Coverage Reporting with Codecov](#coverage-reporting-with-codecov)
    4. [Branch Protection](#branch-protection) 
5. [How to release?](#how-to-release)

# How to use this template

This template provides some basic boilerplate code to get started with new projects. 
The following components are included:

General folder structure for [source code](project_name), [tests](tests), [documentation](docs) and some 
[workflows](.github/workflows) as well as a [.gitignore](.gitignore) file, a [requirements.txt](requirements.txt)
file and the [pyproject.toml](pyproject.toml) file.


## Provided Workflows

### CI

This workflow is designed to automatically build and test code changes pushed to the repository's master 
branch or submitted through a pull request to the master branch.

#### Trigger
The workflow is triggered on two events:

When code changes are pushed to the master branch.
When a pull request is submitted to the master branch.

#### Jobs

The workflow consists of a single job build with the following steps:

**Code Checkout**: The code from the repository's master branch is checked out using the actions/checkout@v3 action.

**Python Setup**: The python-version environment variable is set to one of the following values ["3.8", "3.9", "3.10"] 
using the actions/setup-python@v4 action.

**Dependency Installation**: Required dependencies are installed using the pip install command. The requirements are listed 
in the requirements.txt file. If the file exists, dependencies are installed from it, otherwise, the command will not execute.

**Linting**: The code is linted using the flake8 command. The flake8 command is run twice with different parameters to 
perform two types of linting: error checking and line length checking.

**Test Execution & Report Generation**: The code tests are executed and a coverage report is generated using the
unittest and coverage modules.

**Coverage Upload to Codecov**: If the CODECOV_TOKEN secret is set, the coverage report is uploaded
to Codecov using the codecov/codecov-action@v3 action.

**Package Build**: The source code is packaged using the build module and the resulting package is saved in the dist 
directory.

### Publish Docs

This workflow is designed to automatically generate and publish project documentation to GitHub Pages whenever a 
new tag is pushed to the repository. 

#### Trigger:
The workflow is triggered when a new tag is pushed to the repository.

#### Jobs:
The workflow consists of two jobs `generate` and `publish`:

#### Job: Generate
This job is responsible for generating the project documentation.

- **Code Checkout**: The code from the repository is checked out using the `actions/checkout@v3` action.
- **Python Setup**: The Python environment is set up using the `actions/setup-python@v4` action with the 
`python-version` set to `3.x`.
- **Dependency Installation**: Required dependencies are installed from the `requirements.txt` file using
the `pip install` command.
- **Documentation Generation**: The project documentation is generated using the `pdoc` command. 
The output is saved in the `docs/` directory.
- **Pages Artifact Upload**: The generated documentation is uploaded as an artifact using the 
`actions/upload-pages-artifact@v1` action.

### Job: Publish
This job is responsible for publishing the generated documentation to GitHub Pages.

- **Dependency**: This job depends on the successful completion of the `generate` job.
- **Permissions**: This job requires write access to GitHub Pages and the id-token.
- **Environment**: The environment name and URL for the documentation are set using the `environment` key.
- **Deployment**: The generated documentation is deployed to GitHub Pages using the `actions/deploy-pages@v1` action.
The URL for the deployed documentation can be accessed using `${{ steps.deployment.outputs.page_url }}/project_name`.

### Sync Labels

The Sync Labels workflow will run whenever there is a push to the master branch with changes to either the 
[labels.yml](.github/labels.yml) or [sync-labels.yml](.github/workflows/sync-labels.yml) files.

The job build runs on ubuntu-latest and has two steps. The first step is using the `actions/checkout@v3` action 
to checkout the repository code. The second step uses the `micnncim/action-label-syncer@v1.3.0` action, 
which will synchronize the GitHub repository's labels based on the labels specified in the [labels.yml](.github/labels.yml) 
file. The GITHUB_TOKEN environment variable is set to the GitHub token stored as a secret, which is used 
to authenticate the GitHub API request.

### Release Drafter

The Run Release Drafter job will automatically create a draft release on GitHub using the 
`release-drafter/release-drafter` action.

The draft release will be created when a push is made to the master branch. 
The `GITHUB_TOKEN` environment variable is set to the GitHub token stored as a secret,
which is used to authenticate the GitHub API request.

It uses labels to tag the pull requests and generate the release notes based on synced [labels](.github/labels.yml).

### Enforce Labels

This GitHub Actions workflow enforces the requirement for pull requests to have at least one label from a specified 
list of labels. The list of required labels can be adjusted to fit the needs of the project. 
The workflow also ensures that a banned list of labels are not applied to pull requests.

#### Triggers
The workflow is triggered on the following events for pull requests:
- `labeled`
- `unlabeled`
- `opened`
- `edited`
- `synchronize`

#### Jobs
The workflow consists of a single job, `enforce-label`, which runs on `ubuntu-latest`. 

#### Steps
The job has the following steps:
1. The action `yogevbd/enforce-label-action@2.2.2` is used to enforce the requirement for 
pull requests to have at least one label from the specified list of required labels.
2. The required labels are defined in the `REQUIRED_LABELS_ANY` environment variable as a comma-separated list.
3. The description for the required labels is defined in the `REQUIRED_LABELS_ANY_DESCRIPTION` environment variable.
4. The banned labels are defined in the `BANNED_LABELS` environment variable as a comma-separated list.


### Dependabot

The [dependabot.yaml](.github/dependabot.yaml) is a configuration file for the dependabot service, which updates 
dependencies for a repository. The configuration updates two package ecosystems (pip and github-actions) in the root 
directory of the repository on a weekly interval with pull requests.

## How to include your project as dependency in other projects

You can reference your project as dependency in other projects. Add the following to your `requirements.txt` file:

```txt
<project_name> @ git+ssh://git@github.com/Donner-Reuschel-Luxemburg-S-A/<repository-name>.git@<branch | tag>
```

> ❗ **_NOTE:_**  I generated an extra SSH keypair and added the public key to the personal profile of 
> Simon Symhoven to grant access to the private repositories. The corresponding private key is already added 
> as an organisation secret with name `SSH_PRIVATE_KEY` and is available in each reposiotry by default. 

## Prerequisites

Before you can start with your project, you need to rename `project_name` from template, 
activate GitHub pages and setup Codecov. 

### Rename `project_name`

All occurrences of `project_name` in the files 

* [pyproject.toml](pyproject.toml) line 6, 18 & 22
* [publish-docs.yml](.github/workflows/publish-docs.yml) line 23 & 37
* [.gitignore](.gitignore) line 7

and the directory

* [project_name](project_name)

have to be renamed to your specific project name. 

### Activate GitHub Pages to enable documentation 

Go to `Settings` tab of the repository and click on `Pages`. Then select `GitHub Actions` as `Source`.

### Coverage Reporting with Codecov

Visit [Codecov](https://about.codecov.io/) and login via GitHub. 

To upload test result coverage report to Codecov, you have to setup a Codecov Token for each repository.

Go to [Codecov](https://app.codecov.io/gh/Donner-Reuschel-Luxemburg-S-A/) and select the desired repository. Copy 
the repository upload token (e.g.: `CODECOV_TOKEN=45eadeef-9b47-40b2-912f-a6e94619c522`) and go to the settings 
of the GitHub repository. Under section `Secrets and variables` click `Actions` and add a new repository secret.

Choose `CODECOV_TOKEN` as name and paste the copied id (without `CODECOV_TOKEN=`) to field `Secret`. 

### Branch protection

Go to the `Settings` tab and click on `Branches`. Then press `Add branch protection rule` for branch name pattern `master`.
Then select `Require a pull request before merging` with required number of approvals before merging `1`.
Select also `Require status checks to pass before merging` and press `Create`.

## How to release?

After all relevant pull requests are merged you can release a new version (git tag) in GitHub. Therefor please make sure,
that you bump the version number in a last pull request to the corresponding release drafter version. 
Then press `Publish release`.