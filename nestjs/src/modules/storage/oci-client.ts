import { ObjectStorageClient, models, responses } from 'oci-objectstorage';
import * as common from 'oci-common';
import { ConfigService } from '@nestjs/config';
import { Injectable } from '@nestjs/common';
import * as path from 'node:path';
import * as fs from 'fs';
import * as os from 'os';

@Injectable()
export class OciClient {
    private _client: ObjectStorageClient | null = null;
    private _namespace: string | null = null;
    private _configFilePath: string;

    constructor(private readonly configService: ConfigService) {
        this._configFilePath = path.join(os.homedir(), '.oci', 'config');
    }

    private getClient(): { client: ObjectStorageClient; namespace: string } {
        if (this._client && this._namespace !== null) {
            return { client: this._client, namespace: this._namespace };
        }

        const privateKeyPath =
            process.env.OCI_PRIVATE_KEY_PATH || '/root/.oci/oci_api_key.pem';

        const ociDir = path.dirname(this._configFilePath);
        if (!fs.existsSync(ociDir)) {
            fs.mkdirSync(ociDir, { recursive: true });
        }

        const configContent = `[DEFAULT]
user=${(process.env.OCI_USER || '').trim()}
fingerprint=${(process.env.OCI_FINGERPRINT || '').trim()}
key_file=${privateKeyPath}
tenancy=${(process.env.OCI_TENANCY || '').trim()}
region=${(process.env.OCI_REGION || 'sa-saopaulo-1').trim()}
`;
        fs.writeFileSync(this._configFilePath, configContent.trim());

        const provider = new common.ConfigFileAuthenticationDetailsProvider(this._configFilePath);
        this._client = new ObjectStorageClient({ authenticationDetailsProvider: provider });
        this._namespace =
            process.env.OCI_NAMESPACE ??
            this.configService.get<string>('OCI_NAMESPACE') ??
            '';

        return { client: this._client, namespace: this._namespace };
    }

    async generatePresignedUrl(
        bucketName: string,
        objectKey: string,
        method: 'PUT' | 'GET',
        ttl: number,
    ): Promise<string> {
        const accessType: models.CreatePreauthenticatedRequestDetails.AccessType =
            method === 'GET'
                ? models.CreatePreauthenticatedRequestDetails.AccessType.ObjectRead
                : models.CreatePreauthenticatedRequestDetails.AccessType.ObjectWrite;

        const expirationDate = new Date();
        expirationDate.setSeconds(expirationDate.getSeconds() + ttl);

        const { client, namespace } = this.getClient();
        const response = await client.createPreauthenticatedRequest({
            namespaceName: namespace,
            bucketName,
            createPreauthenticatedRequestDetails: {
                name: `preauth-${Date.now()}`,
                accessType,
                timeExpires: expirationDate,
                objectName: objectKey,
            },
        });

        const region =
            process.env.OCI_REGION ||
            this.configService.get<string>('OCI_REGION') ||
            'sa-saopaulo-1';

        const accessUri = response.preauthenticatedRequest.accessUri;
        const base = `https://objectstorage.${region}.oraclecloud.com`;

        if (accessUri.endsWith('/n/')) {
            const encodedObject = objectKey
                .split('/')
                .map((part) => encodeURIComponent(part))
                .join('/');
            return `${base}${accessUri}${namespace}/b/${bucketName}/o/${encodedObject}`;
        }

        return `${base}${accessUri}`;
    }

    async uploadObject(
        bucketName: string,
        objectKey: string,
        body: Buffer,
        contentType?: string,
    ): Promise<void> {
        const { client, namespace } = this.getClient();
        await client.putObject({
            namespaceName: namespace,
            bucketName,
            objectName: objectKey,
            putObjectBody: body,
            contentLength: body.length,
            contentType,
        });
    }
}
