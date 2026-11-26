import botocore.exceptions

from . import Terminator


class BedrockAgentCoreRuntime(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_agent_runtimes(client):
            agentcore_runtimes = client.get_paginator('list_agent_runtimes').paginate().build_full_result()['agentRuntimes']

            return [] if not agentcore_runtimes else agentcore_runtimes

        return Terminator._create(credentials, BedrockAgentCoreRuntime, 'bedrock-agentcore-control', _paginate_list_agent_runtimes)

    @property
    def created_time(self):
        return self.instance.get("lastUpdatedAt")

    @property
    def id(self):
        return self.instance.get('agentRuntimeId')

    @property
    def name(self):
        return self.instance.get('agentRuntimeName')

    @property
    def ignore(self) -> bool:
        return self.instance.get("status") in ("CREATING", "UPDATING", "DELETING")

    def terminate(self):
        def _paginate_runtime_endpoints():
            runtime_endpoints = self.client.get_paginator('list_agent_runtime_endpoints').paginate(
                agentRuntimeId=self.id).build_full_result()['runtimeEndpoints']

            return [] if not runtime_endpoints else runtime_endpoints

        # Delete non-default runtime endpoints first; the DEFAULT endpoint is
        # auto-created and removed with the runtime itself.
        runtime_endpoints = _paginate_runtime_endpoints()
        for endpoint in runtime_endpoints:
            if endpoint['name'] == 'DEFAULT':
                continue
            self.client.delete_agent_runtime_endpoint(
                agentRuntimeId=self.id,
                endpointName=endpoint['name']
            )

        self.client.delete_agent_runtime(agentRuntimeId=self.id)


class NovaActWorkflowDefinition(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_workflow_definitions(client):
            return client.get_paginator('list_workflow_definitions').paginate().build_full_result()['workflowDefinitionSummaries']

        return Terminator._create(
            credentials, NovaActWorkflowDefinition, 'nova-act', _paginate_workflow_definitions)

    @property
    def created_time(self):
        return self.instance['createdAt']

    @property
    def id(self):
        return self.instance['workflowDefinitionArn']

    @property
    def name(self):
        return self.instance['workflowDefinitionName']

    @property
    def ignore(self):
        return self.instance['status'] == 'DELETING'

    def terminate(self):
        self.client.delete_workflow_definition(workflowDefinitionName=self.name)


class SageMakerAppImageConfig(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_app_image_configs(client):
            configs = client.get_paginator('list_app_image_configs').paginate().build_full_result()['AppImageConfigs']

            return [] if not configs else configs

        return Terminator._create(credentials, SageMakerAppImageConfig, 'sagemaker', _paginate_list_app_image_configs)

    @property
    def created_time(self):
        return self.instance.get('CreationTime')

    @property
    def id(self):
        return self.instance['AppImageConfigArn']

    @property
    def name(self):
        return self.instance['AppImageConfigName']

    def terminate(self):
        self.client.delete_app_image_config(AppImageConfigName=self.name)


class SageMakerCodeRepository(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_code_repositories(client):
            repositories = client.get_paginator('list_code_repositories').paginate().build_full_result()['CodeRepositorySummaryList']

            return [] if not repositories else repositories

        return Terminator._create(credentials, SageMakerCodeRepository, 'sagemaker', _paginate_list_code_repositories)

    @property
    def created_time(self):
        return self.instance.get('CreationTime')

    @property
    def id(self):
        return self.instance['CodeRepositoryArn']

    @property
    def name(self):
        return self.instance['CodeRepositoryName']

    def terminate(self):
        self.client.delete_code_repository(CodeRepositoryName=self.name)


class SageMakerImage(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_images(client):
            images = client.get_paginator('list_images').paginate().build_full_result()['Images']

            return [] if not images else images

        return Terminator._create(credentials, SageMakerImage, 'sagemaker', _paginate_list_images)

    @property
    def created_time(self):
        return self.instance.get('CreationTime')

    @property
    def id(self):
        return self.instance['ImageArn']

    @property
    def name(self):
        return self.instance['ImageName']

    @property
    def ignore(self) -> bool:
        return self.instance.get('ImageStatus') in ('CREATING', 'UPDATING', 'DELETING')

    def terminate(self):
        try:
            self.client.delete_image(ImageName=self.name)
        except botocore.exceptions.ClientError as ex:
            if not ex.response['Error']['Code'] == 'ResourceInUse':
                raise


class SageMakerModel(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_models(client):
            models = client.get_paginator('list_models').paginate().build_full_result()['Models']

            return [] if not models else models

        return Terminator._create(credentials, SageMakerModel, 'sagemaker', _paginate_list_models)

    @property
    def created_time(self):
        return self.instance.get('CreationTime')

    @property
    def id(self):
        return self.instance['ModelArn']

    @property
    def name(self):
        return self.instance['ModelName']

    def terminate(self):
        self.client.delete_model(ModelName=self.name)


class SageMakerEndpointConfig(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_endpoint_configs(client):
            endpoint_configs = client.get_paginator('list_endpoint_configs').paginate().build_full_result()['EndpointConfigs']

            return [] if not endpoint_configs else endpoint_configs

        return Terminator._create(credentials, SageMakerEndpointConfig, 'sagemaker', _paginate_list_endpoint_configs)

    @property
    def created_time(self):
        return self.instance.get('CreationTime')

    @property
    def id(self):
        return self.instance['EndpointConfigArn']

    @property
    def name(self):
        return self.instance['EndpointConfigName']

    def terminate(self):
        self.client.delete_endpoint_config(EndpointConfigName=self.name)


class SageMakerEndpoint(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_endpoints(client):
            endpoints = client.get_paginator('list_endpoints').paginate().build_full_result()['Endpoints']

            return [] if not endpoints else endpoints

        return Terminator._create(credentials, SageMakerEndpoint, 'sagemaker', _paginate_list_endpoints)

    @property
    def created_time(self):
        return self.instance.get('CreationTime')

    @property
    def id(self):
        return self.instance['EndpointArn']

    @property
    def name(self):
        return self.instance['EndpointName']

    @property
    def ignore(self) -> bool:
        return self.instance.get('EndpointStatus').upper() in ('CREATING', 'UPDATING', 'DELETING', 'ROLLING_BACK')

    def terminate(self):
        # Inference components are hosted on the endpoint, so they are removed first. Their deletion is
        # asynchronous, so the endpoint deletion may only succeed on a later run.
        components = self.client.get_paginator('list_inference_components').paginate(EndpointNameEquals=self.name).build_full_result()['InferenceComponents']
        for component in components:
            if component.get('InferenceComponentStatus') != 'Deleting':
                self.client.delete_inference_component(InferenceComponentName=component['InferenceComponentName'])
        self.client.delete_endpoint(EndpointName=self.name)


class SageMakerInferenceComponent(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_inference_components(client):
            components = client.get_paginator('list_inference_components').paginate().build_full_result()['InferenceComponents']

            return [] if not components else components

        return Terminator._create(credentials, SageMakerInferenceComponent, 'sagemaker', _paginate_list_inference_components)

    @property
    def created_time(self):
        return self.instance.get('CreationTime')

    @property
    def id(self):
        return self.instance['InferenceComponentArn']

    @property
    def name(self):
        return self.instance['InferenceComponentName']

    @property
    def ignore(self) -> bool:
        return self.instance.get('InferenceComponentStatus', '').upper() in ('CREATING', 'UPDATING', 'DELETING')

    def terminate(self):
        self.client.delete_inference_component(InferenceComponentName=self.name)


class SageMakerModelPackage(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_model_packages(client):
            packages = client.get_paginator('list_model_packages').paginate().build_full_result()['ModelPackageSummaryList']
            return [] if not packages else packages

        return Terminator._create(credentials, SageMakerModelPackage, 'sagemaker', _paginate_list_model_packages)

    @property
    def created_time(self):
        return self.instance.get('CreationTime')

    @property
    def id(self):
        return self.instance['ModelPackageArn']

    @property
    def name(self):
        return self.instance.get('ModelPackageName') or self.id

    @property
    def ignore(self) -> bool:
        return self.instance.get('ModelPackageStatus') == 'Deleting'

    def terminate(self):
        self.client.delete_model_package(ModelPackageName=self.id)


class SageMakerModelPackageGroup(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_model_package_groups(client):
            groups = client.get_paginator('list_model_package_groups').paginate().build_full_result()['ModelPackageGroupSummaryList']

            return [] if not groups else groups

        return Terminator._create(credentials, SageMakerModelPackageGroup, 'sagemaker', _paginate_list_model_package_groups)

    @property
    def created_time(self):
        return self.instance.get('CreationTime')

    @property
    def id(self):
        return self.instance['ModelPackageGroupArn']

    @property
    def name(self):
        return self.instance['ModelPackageGroupName']

    def terminate(self):
        self.client.delete_model_package_group(ModelPackageGroupName=self.name)


class SageMakerNotebook(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_notebooks(client):
            notebooks = client.get_paginator('list_notebook_instances').paginate().build_full_result()['NotebookInstances']

            return [] if not notebooks else notebooks

        return Terminator._create(credentials, SageMakerNotebook, 'sagemaker', _paginate_list_notebooks)

    @property
    def created_time(self):
        return self.instance.get('CreationTime')

    @property
    def id(self):
        return self.instance['NotebookInstanceArn']

    @property
    def name(self):
        return self.instance['NotebookInstanceName']

    @property
    def ignore(self) -> bool:
        return self.instance.get('NotebookInstanceStatus').upper() in ('PENDING', 'UPDATING', 'DELETING', 'STOPPING')

    def terminate(self):
        def _describe_notebook():
            notebook_info = self.client.describe_notebook_instance(NotebookInstanceName=self.name)
            return notebook_info if notebook_info else {}

        def _stop_notebook(notebook_info):
            if not notebook_info:
                return
            status = notebook_info.get('NotebookInstanceStatus')
            if status != 'Stopped':
                self.client.stop_notebook_instance(NotebookInstanceName=self.name)

        notebook_info = _describe_notebook()
        _stop_notebook(notebook_info=notebook_info)
        self.client.delete_notebook_instance(NotebookInstanceName=self.name)


class SageMakerNotebookLifecycleConfig(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_notebook_lifecycle_configs(client):
            configs = client.get_paginator('list_notebook_instance_lifecycle_configs').paginate().build_full_result()['NotebookInstanceLifecycleConfigs']

            return [] if not configs else configs

        return Terminator._create(credentials, SageMakerNotebookLifecycleConfig, 'sagemaker', _paginate_list_notebook_lifecycle_configs)

    @property
    def created_time(self):
        return self.instance.get('CreationTime')

    @property
    def id(self):
        return self.instance['NotebookInstanceLifecycleConfigArn']

    @property
    def name(self):
        return self.instance['NotebookInstanceLifecycleConfigName']

    def terminate(self):
        self.client.delete_notebook_instance_lifecycle_config(NotebookInstanceLifecycleConfigName=self.name)


class SageMakerFeatureGroup(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_feature_groups(client):
            groups = client.get_paginator('list_feature_groups').paginate().build_full_result()['FeatureGroupSummaries']

            return [] if not groups else groups

        return Terminator._create(credentials, SageMakerFeatureGroup, 'sagemaker', _paginate_list_feature_groups)

    @property
    def created_time(self):
        return self.instance.get('CreationTime')

    @property
    def id(self):
        return self.instance['FeatureGroupArn']

    @property
    def name(self):
        return self.instance['FeatureGroupName']

    @property
    def ignore(self) -> bool:
        # The API rejects deletion while CREATING; DELETING is already in progress.
        return self.instance.get('FeatureGroupStatus', '').upper() in ('CREATING', 'DELETING')

    def terminate(self):
        self.client.delete_feature_group(FeatureGroupName=self.name)


class SageMakerPipeline(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_pipelines(client):
            pipelines = client.get_paginator('list_pipelines').paginate().build_full_result()['PipelineSummaries']

            return [] if not pipelines else pipelines

        return Terminator._create(credentials, SageMakerPipeline, 'sagemaker', _paginate_list_pipelines)

    @property
    def created_time(self):
        return self.instance.get('CreationTime')

    @property
    def id(self):
        return self.instance['PipelineArn']

    @property
    def name(self):
        return self.instance['PipelineName']

    def terminate(self):
        try:
            self.client.delete_pipeline(PipelineName=self.name)
        except botocore.exceptions.ClientError as ex:
            if ex.response['Error']['Code'] not in ('ResourceNotFound', 'ResourceNotFoundException'):
                raise


class SageMakerTrainingJob(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_training_jobs(client):
            return client.get_paginator('list_training_jobs').paginate().build_full_result()['TrainingJobSummaries']

        return Terminator._create(credentials, SageMakerTrainingJob, 'sagemaker', _paginate_list_training_jobs)

    @property
    def created_time(self):
        return self.instance.get('CreationTime')

    @property
    def id(self):
        return self.instance['TrainingJobArn']

    @property
    def name(self):
        return self.instance['TrainingJobName']

    @property
    def ignore(self) -> bool:
        status = self.instance.get('TrainingJobStatus')
        if status == 'InProgress':
            return False
        if status not in ('Stopped', 'Failed', 'Completed'):
            return True

        warm_pool = self.instance.get('WarmPoolStatus') or {}
        return warm_pool.get('Status') == 'Available'

    def terminate(self):
        status = self.instance.get('TrainingJobStatus')
        if status == 'InProgress':
            self.client.update_training_job(
                TrainingJobName=self.name,
                ResourceConfig={'KeepAlivePeriodInSeconds': 0},
            )
            self.client.stop_training_job(TrainingJobName=self.name)
        else:
            self.client.delete_training_job(TrainingJobName=self.name)


class SageMakerDomain(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_domains(client):
            domains = client.get_paginator('list_domains').paginate().build_full_result()['Domains']

            return [] if not domains else domains

        return Terminator._create(credentials, SageMakerDomain, 'sagemaker', _paginate_list_domains)

    @property
    def created_time(self):
        return self.instance.get('CreationTime')

    @property
    def id(self):
        return self.instance['DomainId']

    @property
    def name(self):
        return self.instance['DomainName']

    @property
    def ignore(self) -> bool:
        return self.instance.get('Status').upper() in ('PENDING', 'UPDATING', 'DELETING')

    def terminate(self):
        # By default, all resources are retained (not automatically deleted)
        self.client.delete_domain(DomainId=self.id, RetentionPolicy={'HomeEfsFileSystem': 'Delete'})


class SageMakerUserProfile(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_profiles(client):
            profiles = client.get_paginator('list_user_profiles').paginate().build_full_result()['UserProfiles']

            return [] if not profiles else profiles

        return Terminator._create(credentials, SageMakerUserProfile, 'sagemaker', _paginate_list_profiles)

    @property
    def created_time(self):
        return self.instance.get('CreationTime')

    @property
    def name(self):
        return self.instance['UserProfileName']

    @property
    def ignore(self) -> bool:
        return self.instance.get('Status').upper() in ('PENDING', 'UPDATING', 'DELETING')

    def terminate(self):
        self.client.delete_user_profile(DomainId=self.instance['DomainId'], UserProfileName=self.name)


class SageMakerSpace(Terminator):
    @staticmethod
    def create(credentials):
        def _paginate_list_spaces(client):
            spaces = client.get_paginator('list_spaces').paginate().build_full_result()['Spaces']

            return [] if not spaces else spaces

        return Terminator._create(credentials, SageMakerSpace, 'sagemaker', _paginate_list_spaces)

    @property
    def created_time(self):
        return self.instance.get('CreationTime')

    @property
    def name(self):
        return self.instance['SpaceName']

    @property
    def ignore(self) -> bool:
        return self.instance.get('Status').upper() in ('PENDING', 'UPDATING', 'DELETING')

    def terminate(self):
        self.client.delete_space(DomainId=self.instance['DomainId'], SpaceName=self.name)
