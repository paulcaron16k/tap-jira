# tap-jira

This is a [Singer](https://singer.io) tap that produces JSON-formatted data
following the [Singer
spec](https://github.com/singer-io/getting-started/blob/master/SPEC.md).

This tap:

- Pulls raw data from the [JIRA Cloud REST
  API](https://docs.atlassian.com/jira/REST/cloud/#api/2/)
- Extracts the following resources:
  - [`boards`](https://developer.atlassian.com/cloud/jira/software/rest/api-group-other-operations/#api-agile-1-0-board-get)
  - [`board_issues`](https://developer.atlassian.com/cloud/jira/software/rest/api-group-board/#api-agile-1-0-board-boardid-issue-get)
  - [`board_projects`](https://developer.atlassian.com/cloud/jira/software/rest/api-group-board/#api-agile-1-0-board-boardid-project-get)
  - [`epics`](https://developer.atlassian.com/cloud/jira/software/rest/api-group-board/#api-agile-1-0-board-boardid-epic-get)
  - [`sprints`](https://developer.atlassian.com/cloud/jira/software/rest/api-group-board/#api-agile-1-0-board-boardid-sprint-get)
  - [`board_backlog`](https://developer.atlassian.com/cloud/jira/software/rest/api-group-board/#api-agile-1-0-board-boardid-backlog-get)
  - [`board_configurations`](https://developer.atlassian.com/cloud/jira/software/rest/api-group-board/#api-agile-1-0-board-boardid-configuration-get)
  - [`projects`](https://docs.atlassian.com/jira/REST/cloud/#api/2/project-getAllProjects)
  - [`versions`](https://docs.atlassian.com/jira/REST/cloud/#api/2/project-getProjectVersionsPaginated)
  - [`project_types`](https://docs.atlassian.com/jira/REST/cloud/#api/2/project/type-getAllProjectTypes)
  - [`project_categories`](https://docs.atlassian.com/jira/REST/cloud/#api/2/projectCategory-getAllProjectCategories)
  - [`resolutions`](https://docs.atlassian.com/jira/REST/cloud/#api/2/resolution-getResolutions)
  - [`roles`](https://docs.atlassian.com/jira/REST/cloud/#api/2/role-getProjectRoles)
  - [`users`](https://docs.atlassian.com/jira/REST/cloud/#api/2/user-findUsers)
  - [`issues`](https://docs.atlassian.com/jira/REST/cloud/#api/2/search-search)
  - [`issue_comments`](https://docs.atlassian.com/jira/REST/cloud/#api/2/search-search)
  - [`issue_transitions`](https://docs.atlassian.com/jira/REST/cloud/#api/2/search-search)  
  - [`worklogs`](https://docs.atlassian.com/jira/REST/cloud/#api/2/worklog-getWorklogsForIds)
  - [`issue_fields`](https://developer.atlassian.com/cloud/jira/platform/rest/v2/api-group-issue-fields/#api-rest-api-2-field-get)
  - [`workflow_statuses`](https://developer.atlassian.com/cloud/jira/platform/rest/v2/api-group-workflow-statuses/#api-rest-api-2-status-get)
- Outputs the schema for each resource
- Incrementally pulls data based on the input state

## Quick Start

1. Install

    pip install tap-jira

2. Create the config file

   Create a JSON file called `config.json`. Its contents should look like
   (for Basic Auth):

   ```json
    {
         "start_date": "<i.e. 2017-12-04T19:19:32Z>",
        "username": "<your-jira-username>",
        "password": "<your-jira-password>",
        "base_url": "<https://your-jira-domain>",
        "user_agent": "<user-agent>",
        "timezone": "<i.e. America/New_York>"
    }
    ```

   or (for OAuth):

   ```json
   {
     "oauth_client_secret": "<oauth-client-secret>",
     "user_agent": "<user-agent>",
     "oauth_client_id": "<oauth-client-id>",
     "access_token": "<access-token>",
     "cloud_id": "<cloud-id>",
     "refresh_token": "<refresh-token>",
     "start_date": "<i.e. 2017-12-04T19:19:32Z>",
     "timezone": "<i.e. America/New_York>"
   }
   ```

   The `start_date` specifies the date at which the tap will begin pulling data
   (for those resources that support this).

   For Basic Auth, the `base_url` is the URL where your Jira installation
   can be found. For example, it might look like:
   `https://mycompany.atlassian.net`.

   The `groups` specifies groups for users stream. It is an optional parameter. Default value is `["jira-administrators", "jira-software-users", "jira-core-users", "jira-users", "users"]`.
   `timezone` adjusts dates and timestamps used to incrementally load JIRA data 
   to the timezone specified. It defaults to `UTC`.

4. Run the Tap in Discovery Mode

   ```
   tap-jira -c config.json -d
   ```

   See the Singer docs on discovery mode
   [here](https://github.com/singer-io/getting-started/blob/master/docs/DISCOVERY_MODE.md#discovery-mode).

5. Run the Tap in Sync Mode

   ```
   tap-jira -c config.json -p catalog-file.json
   ```

---

Copyright &copy; 2017 Stitch
