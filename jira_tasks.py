import requests
import os
import argparse
import json
from pygerrit2 import GerritRestAPI, HTTPBasicAuth

jira_api_url = os.environ.get("JIRA_API_URL")
jira_user = os.environ.get("JIRA_USER")
jira_password = os.environ.get("JIRA_PASSWORD")

gerrit_url = os.environ.get("GERRIT_URL")
gerrit_user = os.environ.get("GERRIT_USER")
gerrit_password = os.environ.get("GERRIT_PASSWORD")

gerrit_auth = HTTPBasicAuth(gerrit_user, gerrit_password)
gerrit_api = GerritRestAPI(url=gerrit_url, auth=gerrit_auth)


def get_all_patches_from_issue(issue_number):
    """
    """
    # ================= Get list of links for specific issue ======================
    response = requests.get(f"{jira_api_url}/issue/{issue_number}/remotelink",
                            headers={"Content-Type": "application/json"},
                            auth=tuple([jira_user, jira_password]))
    if response.status_code != 200:
        print("Got unexpected status code for request")
        return []

    list_of_patches = [patch.get("object").get('url')
                        for patch in response.json()
                        if gerrit_url in patch.get("object").get('url')
                       ]
    return list_of_patches



def type_of_issue(issue_number):
    """
    """
    response = requests.get(f"{jira_api_url}/issue/{issue_number}",
                            headers={"Content-Type": "application/json"},
                            auth=(jira_user, jira_password))
    try:
        return response.json().get('fields').get('issuetype').get('name')
    except json.decoder.JSONDecodeError as e:
        print(e)
        print(response)
        return ""

def get_all_subtasks(issue_number):
    jql = f"project = PROD AND 'Epic Link' = '{issue_number}'"

    payload = {'jql': jql,
                "startAt": 0,
                # "maxResults": 25,
                "fields": [
                    "summary",
                    "status",
                    "assignee"
                 ]
             }
    response = requests.get(f"{jira_api_url}/search",
                            params = payload,
                            headers={"Content-Type": "application/json"},
                            auth=(jira_user, jira_password))
    # print(response)
    if response.status_code != 200:
        print("Didn't receive 200 status code for request")
        return []
    # print(json.dumps(response.json(), indent=4))
    return [issue.get('key') for issue in response.json().get('issues')]


def get_patch_link(patch_id):
    return f"{gerrit_url}/#/c/{patch_id}"

class Report:
    def __init__(self, issue, list_of_patches):
        self.issue = issue
        self.list_of_patches = list_of_patches
        self.all_patch_data = None

    def fetch_all_patch_data(self):
        self.all_patch_data = list()
        for patch_url in self.list_of_patches:
            patch_id = patch_url.split("/")[-1]
            change = gerrit_api.get(f"/changes/{patch_id}")
            if change in self.all_patch_data:
                continue
            self.all_patch_data.append(change)

    def head_for_report(self, additional_text):
        return '\n'.join(
            ['=' * 100,
            "= " + f"{additional_text}".center(96) + " =",
            "= " + f"Info for {self.issue}".center(96) + " =",
            '=' * 100
            ]
        )

    def print_common(self):
        if self.all_patch_data is None:
            self.fetch_all_patch_data()
        print(self.head_for_report("COMMON REPORT"))
        print(f"{'number':10} {'subject':70.69} {'project':30} {'branch':30} {'status':10} {'updated':17.16} {'diff':10} ")
        filtred_list = [item for item in self.all_patch_data if isinstance(item, dict) and item.get('subject') and item.get('status')]
        sorted_filtred_list = sorted(filtred_list, key=lambda i: (i.get('subject'), i.get('status')))
        for patch in sorted_filtred_list:
            print("{_number:10} {subject:70.69} {project:30} {branch:30} {status:10} {updated:17.16} +{insertions}:-{deletions}"\
              .format(**patch))

    def print_release(self):
        if self.all_patch_data is None:
            self.fetch_all_patch_data()
        print(self.head_for_report("RELEASE REPORT"))
        # print(self.all_patch_data)
        available_releases = set([patch.get('branch') for patch in self.all_patch_data
            if isinstance(patch, dict) and patch.get('branch')
        ])
        available_projects = set([patch.get('project') for patch in self.all_patch_data
            if isinstance(patch, dict) and patch.get('project')
        ])

        combinations = [(release, project)
                        for release in available_releases
                        for project in available_projects]
        for release_name, project_name  in combinations:
            filtred_list = [patch for patch in self.all_patch_data
                if  isinstance(patch, dict) and patch.get('branch') == release_name and patch.get('project') == project_name]
            if len(filtred_list) == 0:
                continue
            sorted_filtred_list = sorted(filtred_list, key=lambda i: (i['subject'], i['status']))
            print(f"\n * Project {project_name}")
            print(f"Branch {release_name}")
            for patch in sorted_filtred_list:
                print("Commit {change_id:50}  {status:10} {subject:70.69} {link:30}".\
                        format(**patch, link=get_patch_link(patch['_number'])))



################################################################################

def main(issue):
    # issue = 'PROD-31708'
    list_of_patches = list()
    if type_of_issue(issue) in ('Bug', 'User Story'):
        list_of_patches = get_all_patches_from_issue(issue)
    if type_of_issue(issue) in ('Epic'):
        list_of_patches = get_all_patches_from_issue(issue)

        list_of_subtasks = get_all_subtasks(issue)
        for subtask in list_of_subtasks:
            list_of_patches += get_all_patches_from_issue(subtask)

    report = Report(issue, list_of_patches)
    report.print_release()
    report.print_common()

if __name__ == '__main__':
    issue = None
    parser = argparse.ArgumentParser(description='Show info about issue')
    parser.add_argument('issue',
                       help='Issue ID from JIRA')

    args = parser.parse_args()

    main(args.issue)
