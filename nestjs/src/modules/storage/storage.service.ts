import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { OciClient } from './oci-client';

@Injectable()
export class StorageService {
    constructor(
        private readonly ociClient: OciClient,
        private readonly configService: ConfigService,
    ) { }

    private getBucketName(): string {
        return (
            this.configService.get<string>('OCI_BUCKET_NAME') ?? 'vertti-ged'
        );
    }

    private getDownloadTtl(): number {
        return (
            Number(this.configService.get<string>('OCI_DOWNLOAD_TTL_SECONDS')) || 3600
        );
    }

    async uploadBuffer(
        objectKey: string,
        body: Buffer,
        contentType?: string,
    ): Promise<void> {
        const bucketName = this.getBucketName();
        await this.ociClient.uploadObject(bucketName, objectKey, body, contentType);
    }

    async generatePresignedDownloadUrl(objectKey: string): Promise<string> {
        const bucketName = this.getBucketName();
        return this.ociClient.generatePresignedUrl(
            bucketName,
            objectKey,
            'GET',
            this.getDownloadTtl(),
        );
    }
}
