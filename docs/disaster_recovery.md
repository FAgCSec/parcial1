# Plan de Recuperación ante Desastres (Disaster Recovery)

## Proyecto: HeavyCult Dropshipping — Estrategia DR Cross-Region

### 1. Visión General

Este documento detalla la estrategia de recuperación ante desastres (Disaster Recovery Plan) para la arquitectura Big Data de HeavyCult Dropshipping, garantizando la continuidad del negocio y la integridad de los datos ante cualquier fallo catastrófico.

---

### 2. Arquitectura de Replicación Multi-Región

#### 2.1. Topología Primaria-Secundaria

```
┌──────────────────────────────────────────────────────────┐
│                    REGIÓN PRIMARIA                        │
│              (US East - Virginia)                         │
│                                                          │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐ │
│  │ MongoDB     │    │ S3 Bucket    │    │ Lambda      │ │
│  │ Atlas M10   │◄──►│ Primary      │    │ Functions   │ │
│  │ (Shard 1)   │    │ Raw/Proc/Cur │    │             │ │
│  └─────────────┘    └──────────────┘    └─────────────┘ │
│                                                          │
│  ┌─────────────┐    ┌──────────────┐                    │
│  │ MongoDB     │    │ CloudWatch   │                    │
│  │ Atlas M10   │    │ Monitoring   │                    │
│  │ (Shard 2)   │    │ & Alerts     │                    │
│  └─────────────┘    └──────────────┘                    │
└──────────────────────────┬───────────────────────────────┘
                           │  Replicación Asíncrona
                           │  (Change Streams / Oplog)
                           ▼
┌──────────────────────────────────────────────────────────┐
│                    REGIÓN SECUNDARIA                      │
│              (US West - Oregon)                           │
│                                                          │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐ │
│  │ MongoDB     │    │ S3 Bucket    │    │ CloudWatch  │ │
│  │ Atlas M5    │◄──►│ DR Standby   │    │ DR Monitor  │ │
│  │ (Hidden)    │    │ Cross-Region │    │             │ │
│  └─────────────┘    └──────────────┘    └─────────────┘ │
│                                                          │
│  ┌─────────────┐                                         │
│  │ MongoDB     │                                         │
│  │ Atlas M5    │                                         │
│  │ (Arbiter)   │                                         │
│  └─────────────┘                                         │
└──────────────────────────────────────────────────────────┘
```

#### 2.2. Componentes de Replicación

| Componente | Primaria | Secundaria | Tipo |
|------------|----------|------------|------|
| MongoDB Atlas | M10 (US East) | M5 (US West) | Replica Set con Hidden Node |
| S3 Data Lake | us-east-1 | us-west-2 | Cross-Region Replication (CRR) |
| Change Streams | Activos | Replay en DR | Oplog-based |
| CloudWatch | Métricas locales | Métricas cruzadas | Cross-Region Metrics |

---

### 3. Objetivos de Recuperación (RTO/RPO)

#### 3.1. Definición de Objetivos

| Métrica | MongoDB Atlas | Data Lake (S3) | Aplicación |
|---------|---------------|-----------------|------------|
| **RPO** (Recovery Point Objective) | < 5 segundos | < 1 minuto | < 5 minutos |
| **RTO** (Recovery Time Objective) | < 30 segundos | < 5 minutos | < 15 minutos |
| **MTBF** (Mean Time Between Failures) | > 99.99% | > 99.99% | > 99.95% |
| **MTTR** (Mean Time To Recovery) | < 1 minuto | < 5 minutos | < 15 minutos |

#### 3.2. Justificación de RPO/RPO

- **MongoDB RPO < 5s:** Los replica sets de MongoDB Atlas sincronizan el oplog en tiempo real. Con write concern `majority`, cada write se replica al menos a un nodo secundario antes de confirmar. La latencia de replicación cross-region es <5 segundos con el uso de change streams.

- **Data Lake RPO < 1min:** La replicación cross-region de S3 (CRR) sincroniza objetos nuevos en ~ segundos. Los archivos Parquet generados por Spark se escriben en S3 primario y se replican automáticamente.

- **Aplicación RTO < 15min:** La reconexión de la aplicación Python (PyMongo) a la región secundaria se realiza mediante un DNS failover automático con Route 53 health checks.

---

### 4. Políticas de Respaldos Automatizados

#### 4.1. Respaldos de MongoDB Atlas

```
Política de Backups MongoDB Atlas:
═══════════════════════════════

┌────────────┬───────────┬──────────────────────────────┐
│ Frecuencia │ Retención │ Almacenamiento              │
├────────────┼───────────┼──────────────────────────────┤
│ Cada 1h    │ 24h       │ Local (US East)              │
│ Cada 6h    │ 7 días    │ Cross-region (US West)       │
│ Diario     │ 30 días   │ S3 Glacier (archivo)         │
│ Semanal    │ 1 año     │ S3 Glacier Deep Archive      │
│ Mensual    │ 5 años    │ S3 Glacier Deep Archive      │
└────────────┴───────────┴──────────────────────────────┘

Snapshot Automatizado:
- Continuous Backup: Habilitado (oplog-based)
- Scheduled Snapshots: Diario a las 02:00 UTC
- Custom Snapshots: Antes de deployments importantes
- Point-in-Time Recovery: Habilitado (hasta 5s atrás)
```

**Comandos de recuperación:**
```python
# Restauración punto-a-punto
db.command({
    "restoreBackups": 1,
    "snapshotId": "<snapshot_id>",
    "timestamp": "<ISO_timestamp>"
})
```

#### 4.2. Respaldos del Data Lake (S3)

```
Política de Backups S3 Data Lake:
═══════════════════════════════

Raw Layer:
- Versioning: Habilitado
- Cross-Region Replication: Activado (us-east-1 → us-west-2)
- Lifecycle Policy: Transición a IA después de 30 días, Glacier después de 90 días
- Backup: Sync diario a bucket DR mediante AWS Lambda

Processed Layer:
- Versioning: Habilitado
- Lifecycle Policy: Transición a Standard-IA después de 15 días
- Backup: Parquet files replicados cross-region

Curated Layer:
- Versioning: Habilitado
- Lifecycle Policy: Glacier después de 60 días
- Backup: Metadatos en DynamoDB (catálogo)
```

#### 4.3. Script de Backup Automatizado

```python
# scripts/backup_disaster_recovery.py
# Programado con cron o AWS EventBridge
# Ejecuta backups de BD y Data Lake, verifica integridad, envía notificaciones
```

---

### 5. Procedimientos de Failover y Failback

#### 5.1. Escenarios de Fallo

| Escenario | Probabilidad | Acción | Tiempo de Recuperación |
|-----------|-------------|--------|----------------------|
| Fallo de nodo único MongoDB | Alta | Auto-healing de Atlas | < 30s |
| Fallo de región completa | Muy baja | Failover a US West | < 15 min |
| Corrupción de datos | Baja | Point-in-Time Recovery | < 5 min |
| Fallo de S3 primario | Muy baja | CRR promoción a secundario | < 5 min |
| Ataque cibernético/ransomware | Baja | Restauración desde Glacier | < 2 horas |

#### 5.2. Flujo de Failover

```
1. Detección de fallo (CloudWatch alarm → SNS notification)
         │
         ▼
2. Evaluación del impacto (¿region completa o parcial?)
         │
         ├── Fallo parcial → Auto-healing automático
         │
         └── Fallo regional total
              │
              ▼
         3. Promoción del secundario (US West) a primario
              │
              ▼
         4. Actualización DNS (Route 53 failover routing)
              │
              ▼
         5. Reconexión de aplicaciones (PyMongo → nueva URI)
              │
              ▼
         6. Verificación de integridad de datos
              │
              ▼
         7. Notificación a equipo operativo
```

#### 5.3. Flujo de Failback (Recuperación a región primaria)

```
1. Resolución del incidente en región primaria
         │
         ▼
2. Sincronización de datos desde secundario a primaria
         │
         ▼
3. Validación de consistencia de datos (checksums)
         │
         ▼
4. Promoción de primaria a región original
         │
         ▼
5. Restauración de DNS y configuración de aplicaciones
         │
         ▼
6. Monitoreo post-failback (72 horas)
```

---

### 6. Monitoreo y Alertas

#### 6.1. Métricas Críticas

| Métrica | Umbral de Alerta | Acción |
|---------|-----------------|--------|
| Latencia de replicación | > 10 segundos | Escalar secundario |
| Oplog tamaño restante | < 20% | Aumentar oplog size |
| Storage utilizado | > 80% | Escalar cluster |
| Error rate de consultas | > 5% | Activar DR |
| S3 replication lag | > 5 minutos | Verificar CRR |
| Snapshot fallido | Cualquier error | Notificar equipo |

#### 6.2. Herramientas de Monitoreo

- **MongoDB Atlas Alerts:** Configurados para latencia, oplog, storage
- **CloudWatch Alarms:** Métricas de S3, Lambda, Route 53
- **SNS Notifications:** Email y SMS para equipos críticos
- **CloudWatch Dashboard:** Dashboard unificado de toda la infraestructura

---

### 7. Pruebas de Disaster Recovery

#### 7.1. Calendario de Tests

| Tipo de Test | Frecuencia | Duración | Responsable |
|-------------|-----------|----------|-------------|
| Failover automático (nodo) | Mensual | < 30s | DevOps |
| Failover regional completo | Trimestral | < 15 min | Equipo completo |
| Restauración desde backup | Mensual | < 5 min | DBA |
| DR Data Lake (S3) | Trimestral | < 5 min | Data Engineering |
| Simulación de ransomware | Semestral | < 2 horas | Seguridad |
| Documentación de lecciones | Post-cada test | - | Todas áreas |

#### 7.2. Checklist de Prueba DR

```
□ Verificar conexión a región secundaria
□ Confirmar replicación de datos (<5s RPO)
□ Ejecutar failover automático
□ Validar que la aplicación funciona en DR
□ Ejecutar queries de benchmarking en DR
□ Verificar integridad de datos (count_documents)
□ Restaurar desde backup
□ Comparar checksums de datos originales vs restaurados
□ Confirmar failback exitoso
□ Documentar resultados y mejoras
```

---

### 8. Roles y Responsabilidades

| Rol | Responsabilidad |
|-----|----------------|
| **DBA/DB Admin** | MongoDB backups, snapshot management, restore procedures |
| **Data Engineer** | Data Lake backups, ETL pipeline DR, Spark job recovery |
| **DevOps Engineer** | Infrastructure DR, Route 53 failover, CloudWatch setup |
| **Security Engineer** | DR para seguridad, ransomware recovery, access controls |
| **Project Manager** | Coordinación de tests DR, comunicación con stakeholders |

---

### 9. Consideraciones de Costo

| Componente | Costo Mensual Estimado |
|------------|----------------------|
| MongoDB Atlas M10 (Primaria) | ~$100/mes |
| MongoDB Atlas M5 (Secundaria) | ~$50/mes |
| S3 Cross-Region Replication | ~$10/mes |
| S3 Glacier Storage | ~$5/mes |
| CloudWatch + SNS | ~$15/mes |
| Lambda Functions (backup) | ~$5/mes |
| Route 53 Failover | ~$5/mes |
| **Total DR mensual** | **~$190/mes** |

---

### 10. Conclusión

La estrategia de Disaster Recovery cross-region para HeavyCult Dropshipping garantiza:

1. **Disponibilidad del 99.95%+** mediante arquitectura multi-región
2. **RPO < 5 segundos** para datos transaccionales
3. **RPO < 1 minuto** para el Data Lake
4. **RTO < 15 minutos** para recuperación completa
5. **Backups automatizados** con retención de hasta 5 años
6. **Pruebas periódicas** de DR para validar la efectividad
7. **Costo de DR manejable** (~$190/mes) para operaciones críticas

La implementación de este plan DR asegura que el proyecto cumpla con estándares empresariales de continuidad del negocio y protección de datos.

---

*Documento técnico generado para el proyecto HeavyCult Dropshipping — Arquitectura de Datos con MongoDB Atlas.*
