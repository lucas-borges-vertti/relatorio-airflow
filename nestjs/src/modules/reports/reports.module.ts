import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ConfigModule } from '@nestjs/config';
import { StorageModule } from '../storage/storage.module';
import { ReportsController } from './reports.controller';
import { ReportsService } from './reports.service';
import { ReportEntity } from './entities/report.entity';

@Module({
  imports: [TypeOrmModule.forFeature([ReportEntity]), ConfigModule, StorageModule],
  controllers: [ReportsController],
  providers: [ReportsService],
  exports: [ReportsService],
})
export class ReportsModule { }
