import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { StorageService } from './storage.service';
import { OciClient } from './oci-client';

@Module({
    imports: [ConfigModule],
    providers: [StorageService, OciClient],
    exports: [StorageService],
})
export class StorageModule { }
