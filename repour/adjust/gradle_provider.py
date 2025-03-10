import json
import logging
import os
import shutil
import subprocess

from string import Template

from . import process_provider
from . import util
from .. import asutil

logger = logging.getLogger(__name__)

EXECUTION_NAME = "GRADLE"

INIT_SCRIPT_FILE_NAME = "analyzer-init.gradle"
MANIPULATION_FILE_NAME = "manipulation.json"


def get_gradle_provider(init_file_path, default_parameters, specific_indy_group=None, timestamp=None):

    async def adjust(work_dir, extra_adjust_parameters, adjust_result):
        """Generate the manipulation.json file with information about aligned versions"""

        if not os.path.exists(init_file_path):
            raise Exception(
                "The Gradle init file '{}' does not exist - are you sure you provided the correct path in configuration?".format(init_file_path))

        temp_build_parameters = []

        if timestamp:
            temp_build_parameters.append(
                "-DversionIncrementalSuffix=" + timestamp + "-redhat")

        if specific_indy_group:
            temp_build_parameters.append(
                "-DrestRepositoryGroup=" + specific_indy_group)

        extra_parameters, subfolder = util.get_extra_parameters(
            extra_adjust_parameters)

        work_dir = os.path.join(work_dir, subfolder)

        logger.info("Adjusting in {}".format(work_dir))
        logger.info("Copying Gradle init file from '{}'".format(init_file_path))
        shutil.copy2(init_file_path, os.path.join(
            work_dir, INIT_SCRIPT_FILE_NAME))

        logger.info("Getting Gradle version...")

        expect_ok = asutil.expect_ok_closure()

        command_gradle = get_command_gradle(work_dir)

        await expect_ok(
            cmd=[command_gradle, "--version"],
            desc="Failed getting Gradle version",
            cwd=work_dir,
            live_log=True
        )

        cmd = [command_gradle, "--info", "--console", "plain", "--no-daemon", "--stacktrace",
               "--init-script", INIT_SCRIPT_FILE_NAME, "generateAlignmentMetadata"] + default_parameters + temp_build_parameters + extra_parameters

        result = await process_provider.get_process_provider(EXECUTION_NAME,
                                                             cmd,
                                                             get_result_data=get_result_data,
                                                             send_log=True,
                                                             results_file=MANIPULATION_FILE_NAME)(work_dir, extra_adjust_parameters, adjust_result)

        adjust_result["adjustType"] = result["adjustType"]
        adjust_result["resultData"] = result["resultData"]

        return result

    async def get_result_data(work_dir, results_file=None):
        """ Read the manipulation.json file and return it as an object

        Format is:

        {
            VersioningState: {
                executionRootModified: {
                    groupId: "value",
                    artifactId: "value",
                    version: "value"
                }
            },
            RemovedRepositories: []
        }

        """

        template = {
            "VersioningState": {
                "executionRootModified": {
                    "groupId": None,
                    "artifactId": None,
                    "version": None
                }
            },
            "RemovedRepositories": []
        }

        manipulation_file_path = os.path.join(work_dir, MANIPULATION_FILE_NAME)

        logger.info(
            "Reading '{}' file with alignment result".format(manipulation_file_path))

        if not os.path.exists(manipulation_file_path):
            raise Exception("Expected generated alignment file '{}' does not exist".format(
                manipulation_file_path))

        with open(manipulation_file_path, "r") as f:
            result = json.load(f)
            template["VersioningState"]["executionRootModified"]["groupId"] = result["group"]
            template["VersioningState"]["executionRootModified"]["artifactId"] = result["name"]
            template["VersioningState"]["executionRootModified"]["version"] = result["version"]

        try:
            template["RemovedRepositories"] = util.get_removed_repos(
                work_dir, default_parameters)
        except FileNotFoundError as e:
            logger.error('File for removed repositories could not be found')
            logger.error(str(e))

        return template

    return adjust


def get_command_gradle(work_dir):

    # Use system gradle
    command_gradle = 'gradle'

    # If gradlew present, use it instead
    if os.path.isfile(os.path.join(work_dir, './gradlew')):
        command_gradle = './gradlew'

    return command_gradle