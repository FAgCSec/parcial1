import os
import pymongo
from dotenv import load_dotenv
import time
import json

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")


def ejecutar_benchmark():

    print("[LANZAR] Iniciando Benchmarking Analitico de HeavyCult...\n")

    client = pymongo.MongoClient(MONGO_URI)

    # Base de datos correcta
    db = client["bd_erp"]

    # Coleccion OLAP
    coleccion = db["ventas_analiticas"]

    print("[LLAVE] Aplicando estrategias de indexacion analitica...")

    coleccion.create_index(
        [("anio", 1), ("mes", 1)],
        name="idx_fecha"
    )

    coleccion.create_index(
        [("producto.categoria", 1), ("ganancia_neta", -1)],
        name="idx_cat_ganancia"
    )

    coleccion.create_index(
        [("estado", 1), ("cliente.ciudad", 1)],
        name="idx_estado_ciudad"
    )

    coleccion.create_index(
        [("cliente.id", 1), ("total_venta", -1)],
        name="idx_cliente_venta"
    )

    coleccion.create_index(
        [("metodo_pago", 1), ("total_venta", -1)],
        name="idx_metodo_pago"
    )

    coleccion.create_index(
        [("cliente.ciudad", 1), ("costo_flete", -1)],
        name="idx_centro_costo"
    )

    print("[OK] Indices analiticos creados.\n")

    consultas = [

        # ============================================================
        # CONSULTA 1
        # Facturacion y ganancia neta mensual
        # ============================================================
        {
            "nombre": "1. Facturacion y Ganancia Neta Mensual",

            "pipeline": [

                {
                    "$group": {
                        "_id": {
                            "anio": "$anio",
                            "mes": "$mes"
                        },

                        "ventas_totales": {
                            "$sum": "$total_venta"
                        },

                        "ganancia_neta_total": {
                            "$sum": "$ganancia_neta"
                        },

                        "pedidos": {
                            "$sum": 1
                        }
                    }
                },

                {
                    "$sort": {
                        "_id.anio": 1,
                        "_id.mes": 1
                    }
                }
            ]
        },

        # ============================================================
        # CONSULTA 2
        # Top 5 productos mas rentables por categoria
        # ============================================================
        {
            "nombre": "2. Top 5 Productos Mas Rentables por Categoria",

            "pipeline": [

                {
                    "$group": {
                        "_id": {
                            "categoria": "$producto.categoria",
                            "sku": "$producto.sku"
                        },

                        "ganancia": {
                            "$sum": "$ganancia_neta"
                        },

                        "unidades": {
                            "$sum": "$cantidad"
                        }
                    }
                },

                {
                    "$sort": {
                        "_id.categoria": 1,
                        "ganancia": -1
                    }
                },

                {
                    "$group": {
                        "_id": "$_id.categoria",

                        "top_skus": {
                            "$push": {
                                "sku": "$_id.sku",
                                "ganancia": "$ganancia",
                                "unidades": "$unidades"
                            }
                        }
                    }
                },

                {
                    "$project": {
                        "categoria": "$_id",

                        "ranking": {
                            "$slice": [
                                "$top_skus",
                                5
                            ]
                        },

                        "_id": 0
                    }
                }
            ]
        },

        # ============================================================
        # CONSULTA 3
        # Rentabilidad y novedades por ciudad/departamento
        # ============================================================
        {
            "nombre": "3. Rentabilidad y Novedades por Ciudad/Departamento",

            "pipeline": [

                {
                    "$group": {
                        "_id": {
                            "depto": "$cliente.departamento",
                            "ciudad": "$cliente.ciudad"
                        },

                        "ingresos": {
                            "$sum": "$total_venta"
                        },

                        "ganancia_neta": {
                            "$sum": "$ganancia_neta"
                        },

                        "novedades_o_cancelados": {
                            "$sum": {
                                "$cond": [
                                    {
                                        "$in": [
                                            "$estado",
                                            [
                                                "novelty",
                                                "cancelled"
                                            ]
                                        ]
                                    },
                                    1,
                                    0
                                ]
                            }
                        }
                    }
                },

                {
                    "$sort": {
                        "ingresos": -1
                    }
                }
            ]
        },

        # ============================================================
        # CONSULTA 4
        # Proporcion de entregas exitosas vs novedades
        # ============================================================
        {
            "nombre": "4. Proporcion de Entregas Exitosas vs Novedades (COD)",

            "pipeline": [

                {
                    "$group": {
                        "_id": "$estado",

                        "total_pedidos": {
                            "$sum": 1
                        },

                        "monto_acumulado": {
                            "$sum": "$total_venta"
                        }
                    }
                },

                {
                    "$sort": {
                        "total_pedidos": -1
                    }
                }
            ]
        },

        # ============================================================
        # CONSULTA 5
        # Top 10 Clientes por Gasto Total (RFM)
        # ============================================================
        {
            "nombre": "5. Top 10 Clientes por Gasto Total (RFM)",

            "pipeline": [

                {
                    "$group": {
                        "_id": "$cliente.id",

                        "nombre": {"$first": "$cliente.nombre"},
                        "ciudad": {"$first": "$cliente.ciudad"},
                        "gasto_total": {"$sum": "$total_venta"},
                        "total_compras": {"$sum": 1},
                        "ticket_promedio": {"$avg": "$total_venta"}
                    }
                },

                {
                    "$sort": {"gasto_total": -1}
                },

                {
                    "$limit": 10
                },

                {
                    "$project": {
                        "_id": 1,
                        "nombre": 1,
                        "ciudad": 1,
                        "gasto_total": {"$round": ["$gasto_total", 2]},
                        "total_compras": 1,
                        "ticket_promedio": {"$round": ["$ticket_promedio", 2]},
                        "_id": 0
                    }
                }
            ]
        },

        # ============================================================
        # CONSULTA 6
        # Ventas por Metodo de Pago
        # ============================================================
        {
            "nombre": "6. Ventas por Metodo de Pago",

            "pipeline": [

                {
                    "$group": {
                        "_id": "$metodo_pago",

                        "total_ordenes": {"$sum": 1},
                        "ingresos_totales": {"$sum": "$total_venta"},
                        "ticket_promedio": {"$avg": "$total_venta"}
                    }
                },

                {
                    "$sort": {"ingresos_totales": -1}
                },

                {
                    "$project": {
                        "metodo_pago": "$_id",
                        "total_ordenes": 1,
                        "ingresos_totales": {"$round": ["$ingresos_totales", 2]},
                        "ticket_promedio": {"$round": ["$ticket_promedio", 2]},
                        "_id": 0
                    }
                }
            ]
        },

        # ============================================================
        # CONSULTA 7
        # Ventas por Dia de la Semana
        # ============================================================
        {
            "nombre": "7. Ventas por Dia de la Semana",

            "pipeline": [

                {
                    "$group": {
                        "_id": {"anio": "$anio", "mes": "$mes", "dia": "$dia"},

                        "total_ventas": {"$sum": "$total_venta"},
                        "total_ordenes": {"$sum": 1},
                        "ticket_promedio": {"$avg": "$total_venta"}
                    }
                },

                {
                    "$sort": {"_id.anio": 1, "_id.mes": 1, "_id.dia": 1}
                },

                {
                    "$project": {
                        "fecha": {"$dateFromParts": {
                            "year": "$_id.anio",
                            "month": "$_id.mes",
                            "day": "$_id.dia"
                        }},
                        "total_ventas": 1,
                        "total_ordenes": 1,
                        "ticket_promedio": {"$round": ["$ticket_promedio", 2]},
                        "_id": 0
                    }
                }
            ]
        },

        # ============================================================
        # CONSULTA 8
        # Rendimiento por Categoria de Producto
        # ============================================================
        {
            "nombre": "8. Rendimiento por Categoria de Producto",

            "pipeline": [

                {
                    "$group": {
                        "_id": "$producto.categoria",

                        "ventas_totales": {"$sum": "$total_venta"},
                        "ganancia_neta_total": {"$sum": "$ganancia_neta"},
                        "unidades_vendidas": {"$sum": "$cantidad"},
                        "num_productos": {"$addToSet": "$producto.sku"}
                    }
                },

                {
                    "$sort": {"ventas_totales": -1}
                },

                {
                    "$project": {
                        "categoria": "$_id",
                        "ventas_totales": {"$round": ["$ventas_totales", 2]},
                        "ganancia_neta_total": {"$round": ["$ganancia_neta_total", 2]},
                        "unidades_vendidas": 1,
                        "num_productos": {"$size": "$num_productos"},
                        "margen_promedio": {
                            "$cond": [
                                {"$gt": ["$ventas_totales", 0]},
                                {"$multiply": [
                                    {"$divide": ["$ganancia_neta_total", "$ventas_totales"]},
                                    100
                                ]},
                                0
                            ]
                        },
                        "_id": 0
                    }
                }
            ]
        },

        # ============================================================
        # CONSULTA 9
        # Costo de Flete por Ciudad
        # ============================================================
        {
            "nombre": "9. Costo de Flete por Ciudad",

            "pipeline": [

                {
                    "$group": {
                        "_id": {
                            "ciudad": "$cliente.ciudad",
                            "departamento": "$cliente.departamento"
                        },

                        "costo_flete_total": {"$sum": "$costo_flete"},
                        "costo_flete_promedio": {"$avg": "$costo_flete"},
                        "total_ventas": {"$sum": "$total_venta"},
                        "pedidos": {"$sum": 1}
                    }
                },

                {
                    "$sort": {"costo_flete_total": -1}
                },

                {
                    "$project": {
                        "ciudad": "$_id.ciudad",
                        "departamento": "$_id.departamento",
                        "costo_flete_total": {"$round": ["$costo_flete_total", 2]},
                        "costo_flete_promedio": {"$round": ["$costo_flete_promedio", 2]},
                        "total_ventas": {"$round": ["$total_ventas", 2]},
                        "pedidos": 1,
                        "flete_por_venta": {
                            "$divide": ["$costo_flete_total", "$total_ventas"]
                        },
                        "_id": 0
                    }
                }
            ]
        },

        # ============================================================
        # CONSULTA 10
        # Ventas Trimestrales por Ano
        # ============================================================
        {
            "nombre": "10. Ventas Trimestrales por Ano",

            "pipeline": [

                {
                    "$group": {
                        "_id": {
                            "anio": "$anio",
                            "trimestre": {"$ceil": {"$divide": ["$mes", 3]}}
                        },

                        "ventas_totales": {"$sum": "$total_venta"},
                        "ganancia_neta_total": {"$sum": "$ganancia_neta"},
                        "total_ordenes": {"$sum": 1}
                    }
                },

                {
                    "$sort": {"_id.anio": 1, "_id.trimestre": 1}
                },

                {
                    "$project": {
                        "anio": "$_id.anio",
                        "trimestre": "$_id.trimestre",
                        "ventas_totales": {"$round": ["$ventas_totales", 2]},
                        "ganancia_neta_total": {"$round": ["$ganancia_neta_total", 2]},
                        "total_ordenes": 1,
                        "_id": 0
                    }
                }
            ]
        }
    ]

    print(
        "[ENGRAJE] Ejecutando benchmark de consultas...\n"
        + "-" * 70
    )

    tiempos = []

    for consulta in consultas:

        print(f"[PLAY] {consulta['nombre']}")

        inicio = time.perf_counter()

        resultados = list(
            coleccion.aggregate(
                consulta["pipeline"],
                allowDiskUse=True
            )
        )

        fin = time.perf_counter()

        tiempo_ms = (fin - inicio) * 1000

        tiempos.append(tiempo_ms)

        print(
            f"    [CRONOMETRO] Latencia: "
            f"{tiempo_ms:.2f} ms | "
            f"Resultados: {len(resultados)}"
        )

        if len(resultados) > 0:

            muestra = json.loads(
                json.dumps(
                    resultados[0],
                    default=str
                )
            )

            print(f"    [BOMBILLA] Muestra: {muestra}")

        print("-" * 70)

    promedio = sum(tiempos) / len(tiempos)

    print("\n" + "=" * 70)

    print("[GRAFICO] RESUMEN DE RENDIMIENTO DE CONSULTAS")

    print("=" * 70)

    print(
        f"[CRONOMETRO] Latencia promedio: "
        f"{promedio:.2f} ms"
    )

    print(
        f"[LANZAR] Latencia maxima: "
        f"{max(tiempos):.2f} ms"
    )

    print(
        f"[CAJA] Documentos procesados: "
        f"{coleccion.count_documents({})}"
    )

    print("=" * 70)

    client.close()


if __name__ == "__main__":
    ejecutar_benchmark()