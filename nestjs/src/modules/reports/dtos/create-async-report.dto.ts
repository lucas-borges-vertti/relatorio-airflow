import { IsNotEmpty, IsObject, IsString, IsEmail, IsOptional, IsArray, ValidateNested } from 'class-validator';
import { Type } from 'class-transformer';

export class PerodoDto {
  @IsString()
  @IsNotEmpty()
  ini: string;

  @IsString()
  @IsNotEmpty()
  fim: string;
}

export class CreateAsyncReportDto {
  @IsString()
  @IsNotEmpty()
  action: string;

  @ValidateNested()
  @Type(() => PerodoDto)
  periodos: PerodoDto[];

  /** Enviado pelo frontend como cliente (App.user.cliente) */
  @IsOptional()
  @IsString()
  cliente?: string;

  @IsOptional()
  @IsString()
  cliente_cnpj?: string;

  /** E-mail de entrega do relatório (enviado pelo frontend no campo email) */
  @IsOptional()
  @IsEmail()
  email?: string;

  @IsOptional()
  @IsEmail()
  usuario_email?: string;

  // Filtros equivalentes aos parâmetros do PHP getAnalitic
  @IsOptional()
  @IsString()
  id_pro?: string;

  @IsOptional()
  @IsArray()
  cnpjund?: string[];

  @IsOptional()
  @IsArray()
  cnpjparceiro?: string[];

  @IsOptional()
  @IsArray()
  remetentes?: string[];

  @IsOptional()
  @IsArray()
  destinatarios?: string[];

  @IsOptional()
  @IsArray()
  recebedores?: string[];

  @IsOptional()
  @IsString()
  operacao?: string;

  @IsOptional()
  @IsString()
  id_rv?: string;

  @IsOptional()
  @IsString()
  modal?: string;

  @IsOptional()
  aprovacoes?: any;

  @IsOptional()
  @IsString()
  contrato?: string;

  @IsOptional()
  @IsObject()
  filtros?: Record<string, any>;

  @IsOptional()
  @IsString()
  usuario_id?: string;

  @IsOptional()
  @IsString()
  version?: string;

  @IsOptional()
  @IsString()
  token?: string;

  @IsOptional()
  @IsString()
  hmac?: string;

  // Remaining payload fields
  [key: string]: any;
}
