import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn, UpdateDateColumn } from 'typeorm';

export enum ReportStatus {
  PENDING = 'PENDING',
  PROCESSING = 'PROCESSING',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
  CANCELLED = 'CANCELLED',
}

@Entity('velog_reports_async')
export class ReportEntity {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column()
  request_id: string;

  @Column({ type: 'enum', enum: ReportStatus, default: ReportStatus.PENDING })
  status: ReportStatus;

  @Column({ type: 'json' })
  payload: object;

  @Column()
  cliente_cnpj: string;

  @Column()
  usuario_id: number;

  @Column({ nullable: true })
  usuario_email: string;

  @Column({ type: 'json', nullable: true })
  filtros: object;

  @Column({ nullable: true })
  periodo_ini: string;

  @Column({ nullable: true })
  periodo_fim: string;

  @Column({ nullable: true })
  airflow_dag_run_id: string;

  @Column({ nullable: true })
  error_message: string;

  @Column({ type: 'json', nullable: true })
  resultado: object;

  @CreateDateColumn()
  created_at: Date;

  @UpdateDateColumn()
  updated_at: Date;

  @Column({ nullable: true })
  completed_at: Date;

  @Column({ nullable: true })
  delivered_at: Date;

  @Column({ nullable: true })
  object_key_pdf: string;

  @Column({ nullable: true })
  object_key_csv: string;
}
