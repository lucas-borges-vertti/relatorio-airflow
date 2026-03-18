import { Controller, Post, Get, Patch, Body, Param, Query, HttpStatus, HttpCode, BadRequestException } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { ReportsService } from './reports.service';
import { CreateAsyncReportDto } from './dtos/create-async-report.dto';

@ApiTags('reports')
@Controller('api/reports')
export class ReportsController {
  constructor(private readonly reportsService: ReportsService) { }

  @Post('async')
  @HttpCode(HttpStatus.ACCEPTED)
  @ApiOperation({ summary: 'Submeter relatório assíncrono' })
  @ApiResponse({
    status: 202,
    description: 'Relatório enfileirado com sucesso',
    schema: {
      example: {
        status: true,
        requestId: 'uuid-xxx',
        message: 'Relatório enfileirado com sucesso',
        data: {
          id: 'uuid-xxx',
          status: 'PENDING',
          created_at: '2026-03-16T10:00:00Z',
        },
      },
    },
  })
  async submitAsyncReport(@Body() createReportDto: CreateAsyncReportDto) {
    try {
      const report = await this.reportsService.createAsyncReport(createReportDto);
      return {
        status: true,
        requestId: report.request_id,
        message: 'Relatório enfileirado com sucesso',
        data: report,
      };
    } catch (error) {
      throw new BadRequestException({
        status: false,
        message: (error as Error).message || 'Erro ao processar relatório',
      });
    }
  }

  @Get(':id/status')
  @ApiOperation({ summary: 'Obter status do relatório' })
  @ApiResponse({
    status: 200,
    description: 'Status do relatório',
    schema: {
      example: {
        status: true,
        data: {
          id: 'uuid-xxx',
          status: 'PROCESSING',
          created_at: '2026-03-16T10:00:00Z',
          updated_at: '2026-03-16T10:05:00Z',
        },
      },
    },
  })
  async getReportStatus(@Param('id') reportId: string) {
    const report = await this.reportsService.getReportById(reportId);
    if (!report) {
      throw new BadRequestException({
        status: false,
        message: 'Relatório não encontrado',
      });
    }
    return {
      status: true,
      data: report,
    };
  }

  @Get()
  @ApiOperation({ summary: 'Listar relatórios (filtro opcional: ?status=PENDING|PROCESSING|COMPLETED|FAILED)' })
  async findAll(
    @Query('status') status?: string,
    @Query('limit') limit?: string,
  ) {
    const reports = await this.reportsService.findAll(status, limit ? parseInt(limit) : 50);
    return {
      status: true,
      count: reports.length,
      data: reports,
    };
  }

  @Get('pending')
  @ApiOperation({ summary: 'Listar relatórios pendentes (para Airflow)' })
  async getPendingReports() {
    const reports = await this.reportsService.getPendingReports();
    return {
      status: true,
      count: reports.length,
      data: reports,
    };
  }

  @Patch(':id/status')
  @ApiOperation({ summary: 'Atualizar status do relatório (callback Airflow)' })
  async updateReportStatus(
    @Param('id') reportId: string,
    @Body()
    updateDto: {
      status: string;
      error_message?: string;
      airflow_dag_run_id?: string;
      resultado?: object;
    },
  ) {
    try {
      const report = await this.reportsService.updateReportStatus(
        reportId,
        updateDto.status,
        updateDto.error_message,
        updateDto.resultado,
        updateDto.airflow_dag_run_id,
      );
      return {
        status: true,
        message: 'Status atualizado com sucesso',
        data: report,
      };
    } catch (error) {
      throw new BadRequestException({
        status: false,
        message: (error as Error).message,
      });
    }
  }

  @Patch(':id/delivered')
  @ApiOperation({ summary: 'Marcar como entregue' })
  async markAsDelivered(@Param('id') reportId: string) {
    const report = await this.reportsService.markAsDelivered(reportId);
    return {
      status: true,
      message: 'Relatório marcado como entregue',
      data: report,
    };
  }
}
