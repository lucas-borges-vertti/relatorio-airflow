import { Injectable, InternalServerErrorException, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { ConfigService } from '@nestjs/config';
import { randomUUID } from 'crypto';
import axios from 'axios';
import { ReportEntity, ReportStatus } from './entities/report.entity';
import { CreateAsyncReportDto } from './dtos/create-async-report.dto';

@Injectable()
export class ReportsService {
  private readonly logger = new Logger(ReportsService.name);

  constructor(
    @InjectRepository(ReportEntity)
    private readonly reportRepository: Repository<ReportEntity>,
    private readonly configService: ConfigService,
  ) { }

  async createAsyncReport(createReportDto: CreateAsyncReportDto): Promise<ReportEntity> {
    try {
      const requestId = randomUUID();

      const report = this.reportRepository.create({
        request_id: requestId,
        status: ReportStatus.PENDING,
        payload: createReportDto,
        cliente_cnpj: createReportDto.cliente_cnpj || createReportDto.cliente || '',
        usuario_email: createReportDto.email || createReportDto.usuario_email,
        usuario_id: parseInt(createReportDto.usuario_id || '0'),
        filtros: {
          id_pro: createReportDto.id_pro ?? '-1',
          cnpjund: createReportDto.cnpjund ?? [],
          cnpjparceiro: createReportDto.cnpjparceiro ?? [],
          remetentes: createReportDto.remetentes ?? [],
          destinatarios: createReportDto.destinatarios ?? [],
          recebedores: createReportDto.recebedores ?? [],
          operacao: createReportDto.operacao ?? 'T',
          id_rv: createReportDto.id_rv ?? '',
          modal: createReportDto.modal ?? 'TODOS',
          aprovacoes: createReportDto.aprovacoes ?? [],
          contrato: createReportDto.contrato ?? '',
        },
        periodo_ini: createReportDto.periodos?.[0]?.ini,
        periodo_fim: createReportDto.periodos?.[0]?.fim,
      });

      const savedReport = await this.reportRepository.save(report);

      // Trigger Airflow DAG
      await this.triggerAirflowDag(savedReport);

      return savedReport;
    } catch (error) {
      this.logger.error('Error creating async report', error);
      throw new InternalServerErrorException('Falha ao criar relatório');
    }
  }

  async triggerAirflowDag(report: ReportEntity): Promise<void> {
    try {
      const airflowUrl = this.configService.get('AIRFLOW_BASE_URL');
      const dagId = this.configService.get('AIRFLOW_DAG_ID');
      const username = this.configService.get('AIRFLOW_API_USER');
      const password = this.configService.get('AIRFLOW_API_PASSWORD');

      const auth = {
        username,
        password,
      };

      const dagRunConfig = {
        report_id: report.id,
        request_id: report.request_id,
        payload: report.payload,
        cliente: (report.payload as any)?.cliente || report.cliente_cnpj,
        cliente_cnpj: report.cliente_cnpj,
        usuario_email: report.usuario_email,
      };

      const response = await axios.post(
        `${airflowUrl}/api/v1/dags/${dagId}/dagRuns`,
        {
          conf: dagRunConfig,
        },
        { auth },
      );

      this.logger.log(`Airflow DAG triggered: ${response.data.dag_run_id}`);

      // Update report with DAG run ID
      await this.reportRepository.update(report.id, {
        airflow_dag_run_id: response.data.dag_run_id,
        status: ReportStatus.PROCESSING,
      });
    } catch (error) {
      this.logger.error('Error triggering Airflow DAG', error);
      // Don't throw - report is already saved, Airflow trigger is async
      // Airflow can be triggered manually if needed
    }
  }

  async getReportById(reportId: string): Promise<ReportEntity | null> {
    return this.reportRepository.findOne({ where: { id: reportId } });
  }

  async getPendingReports(limit: number = 10): Promise<ReportEntity[]> {
    return this.reportRepository.find({
      where: { status: ReportStatus.PENDING },
      order: { created_at: 'ASC' },
      take: limit,
    });
  }

  async findAll(status?: string, limit: number = 50): Promise<ReportEntity[]> {
    const where = status && Object.values(ReportStatus).includes(status as ReportStatus)
      ? { status: status as ReportStatus }
      : {};
    return this.reportRepository.find({
      where,
      order: { created_at: 'DESC' },
      take: limit,
    });
  }

  async updateReportStatus(
    reportId: string,
    status: string,
    errorMessage?: string,
    resultado?: object,
    airflowDagRunId?: string,
  ): Promise<ReportEntity> {
    try {
      const validStatus = Object.values(ReportStatus).includes(status as ReportStatus)
        ? (status as ReportStatus)
        : ReportStatus.FAILED;

      const updateData: any = {
        status: validStatus,
      };

      if (errorMessage) {
        updateData.error_message = errorMessage;
      }

      if (resultado) {
        updateData.resultado = resultado;
      }

      if (airflowDagRunId) {
        updateData.airflow_dag_run_id = airflowDagRunId;
      }

      if (validStatus === ReportStatus.COMPLETED || validStatus === ReportStatus.FAILED) {
        updateData.completed_at = new Date();
      }

      await this.reportRepository.update(reportId, updateData);

      return this.getReportById(reportId) as unknown as ReportEntity;
    } catch (error) {
      this.logger.error('Error updating report status', error);
      throw new InternalServerErrorException('Falha ao atualizar status');
    }
  }

  async markAsDelivered(reportId: string): Promise<ReportEntity> {
    await this.reportRepository.update(reportId, {
      delivered_at: new Date(),
    });
    return this.getReportById(reportId) as unknown as ReportEntity;
  }
}
