import json
import logging
import os
import shlex
import tempfile

from . import process_provider
from .. import exception

logger = logging.getLogger(__name__)

def get_project_manipulator_provider(execution_name, jar_path, default_parameters, specific_indy_group, timestamp):

    async def get_result_data(work_dir, results_file=None):
        
        raw_result_data = "{}"
        if results_file:
            results_file_path = results_file
        else:
            raise Exception("Could not figure out path of results from alignment")

        if os.path.isfile(results_file_path):
            with open(results_file_path, "r") as file:
                raw_result_data = file.read()

            # delete results file afterwards
            os.remove(results_file_path)

        logger.info('Got project manipulator result data "{raw_result_data}".'.format(**locals()))

        result_data = json.loads(raw_result_data)

        result_data['RemovedRepositories'] = []

        return result_data


    async def get_extra_parameters(extra_adjust_parameters):
        """
        Get the extra CUSTOM_PROJECT_MANIPULATOR_PARAMETERS parameters from PNC
        """
        subfolder = ''

        paramsString = extra_adjust_parameters.get("CUSTOM_PROJECT_MANIPULATOR_PARAMETERS", None)
        if paramsString is None:
            return []
        else:
            params = shlex.split(paramsString)
            for p in params:
                if p[0] != "-":
                    desc = ('Parameters that do not start with dash "-" are not allowed. '
                            + 'Found "{p}" in "{params}".'.format(**locals()))
                    raise exception.AdjustCommandError(desc, [], 10, stderr=desc)

            return params

    async def adjust(work_dir, extra_adjust_parameters, adjust_result):
        nonlocal execution_name

        temp_build_parameters = []

        if timestamp:
            temp_build_parameters.append("-DversionIncrementalSuffix=" + timestamp + "-redhat")

        if specific_indy_group:
            temp_build_parameters.append("-DrestRepositoryGroup=" + specific_indy_group)

        extra_parameters = await get_extra_parameters(extra_adjust_parameters)

        filename = tempfile.NamedTemporaryFile(delete=False).name

        cmd = ["java", "-jar", jar_path] + default_parameters + temp_build_parameters + extra_parameters + \
              ['--result=' + filename]

        logger.info('Executing "' + execution_name + '" Command is "{cmd}".'.format(**locals()))

        res = await process_provider.get_process_provider(execution_name,
                                                     cmd,
                                                     get_result_data=get_result_data,
                                                     send_log=True,
                                                     results_file=filename) \
            (work_dir, extra_adjust_parameters, adjust_result)

        # TODO: need to detect when it is disabled and grab the version otherwise

        adjust_result['resultData'] = res['resultData']

        return res

    return adjust


async def get_version_from_result(data):
    """
    Format of project_manipulator_result should be as follows:

    {
        "name": "<name>",
        "version": "<version>"
    }

    Function tries to extract version generated by PME from the pme_result

    Parameters:
    - data: :dict:
    """
    try:
        version = data['version']
        return version
    except  Exception as e:
        logger.error("Couldn't extract Project Manipulator result version from JSON file")
        logger.error(e)
        return None
