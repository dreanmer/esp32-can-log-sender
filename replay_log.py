
#!/usr/bin/env python3
import serial
import time
import csv
import sys
import signal

class CanLogReplayer:
    def __init__(self, port='/dev/ttyACM1', speed_factor=1.0):
        self.port = port
        self.speed_factor = speed_factor
        self.serial_conn = None
        self.running = True
        self.auto_adjust = True
        self.adjustment_interval = 1000  # Ajustar a cada 1000 mensagens
        self.max_speed_factor = 5.0  # Velocidade máxima
        self.min_speed_factor = 0.1  # Velocidade mínima

    def connect(self):
        """Conecta à porta serial"""
        try:
            self.serial_conn = serial.Serial(self.port, 115200, timeout=1)
            time.sleep(2)  # Aguarda estabilização
            print(f"Conectado a {self.port}!")
            return True
        except Exception as e:
            print(f"Erro ao conectar: {e}")
            return False

    def calculate_speed_adjustment(self, real_time, log_time):
        """Calcula o fator de ajuste de velocidade baseado no atraso"""
        if log_time <= 0:
            return self.speed_factor

        # Calcula o atraso atual
        delay_ratio = real_time / log_time

        # Se estamos atrasados, aumenta a velocidade
        if delay_ratio > 1.0:
            # Fator de correção proporcional ao atraso
            adjustment_factor = delay_ratio * 1.2  # 20% de margem para correção
            new_speed = self.speed_factor * adjustment_factor
        else:
            # Se estamos adiantados, reduz a velocidade gradualmente
            new_speed = self.speed_factor * 0.95

        # Limita os valores extremos
        new_speed = max(self.min_speed_factor, min(self.max_speed_factor, new_speed))

        return new_speed

    def send_can_message(self, timestamp, msg_id, dlc, data):
        """Envia mensagem CAN via serial no formato esperado pelo ESP32"""
        if not self.serial_conn:
            return False

        try:
            # Formato esperado pelo ESP32: timestamp,id,dlc,data0,data1,data2...
            data_str = ','.join(f'{byte:02X}' for byte in data[:dlc])
            command = f"{timestamp},{msg_id:08X},{dlc},{data_str}\n"

            self.serial_conn.write(command.encode())

            # Aguarda confirmação do ESP32
            response = self.serial_conn.readline().decode().strip()
            return response == "OK"

        except Exception as e:
            print(f"Erro ao enviar mensagem: {e}")
            return False

    def parse_csv_row(self, row):
        """Parse de uma linha do CSV"""
        try:
            # Timestamp
            timestamp = float(row['Time Stamp'])

            # ID da mensagem
            msg_id = int(row['ID'], 16)

            # DLC (Length)
            dlc = int(row['LEN'])
            if dlc > 8:
                dlc = 8

            # Dados da mensagem (D1-D8)
            data = []
            for i in range(1, 9):
                col_name = f'D{i}'
                if col_name in row and row[col_name].strip():
                    try:
                        data.append(int(row[col_name], 16))
                    except ValueError:
                        data.append(0)
                else:
                    data.append(0)

            return timestamp, msg_id, dlc, data

        except (ValueError, KeyError) as e:
            print(f"Erro ao fazer parse da linha: {e}")
            print(f"Linha: {row}")
            return None, None, None, None

    def replay_log(self, log_file):
        """Reproduz o arquivo de log com correção automática de velocidade"""
        if not self.connect():
            return

        print(f"=== REPRODUTOR DE LOG CAN ===")
        print(f"Arquivo: {log_file}")
        print(f"Porta: {self.port}")
        print(f"Velocidade inicial: {self.speed_factor}x")
        print(f"Correção automática: {'Ativada' if self.auto_adjust else 'Desativada'}")
        print("Pressione Ctrl+C para interromper\n")

        try:
            with open(log_file, 'r') as f:
                reader = csv.DictReader(f)
                messages = list(reader)

            print(f"Total de mensagens: {len(messages)}")
            print("Iniciando reprodução...\n")

            start_time = time.time()
            first_log_time = None
            sent_count = 0
            error_count = 0

            for i, row in enumerate(messages):
                if not self.running:
                    break

                timestamp, msg_id, dlc, data = self.parse_csv_row(row)
                if timestamp is None:
                    error_count += 1
                    continue

                if first_log_time is None:
                    first_log_time = timestamp
                    last_log_time = timestamp
                else:
                    # Calcula o delay necessário
                    log_delta = (timestamp - last_log_time) / 1000000.0  # Converter para segundos
                    adjusted_delay = log_delta / self.speed_factor

                    if adjusted_delay > 0:
                        time.sleep(adjusted_delay)

                    last_log_time = timestamp

                # Envia a mensagem
                if self.send_can_message(timestamp, msg_id, dlc, data):
                    sent_count += 1

                    # A cada intervalo definido, ajusta a velocidade
                    if (self.auto_adjust and
                            sent_count % self.adjustment_interval == 0 and
                            sent_count > 0):

                        current_real_time = time.time() - start_time
                        current_log_time = (timestamp - first_log_time) / 1000000.0

                        old_speed = self.speed_factor
                        self.speed_factor = self.calculate_speed_adjustment(
                            current_real_time, current_log_time)

                        # Log do ajuste
                        delay_ms = (current_real_time - current_log_time) * 1000000.0
                        print(f"Ajuste de velocidade: {old_speed:.2f}x → {self.speed_factor:.2f}x "
                              f"(Atraso: {delay_ms:.0f}ms)")

                    # Status a cada 100 mensagens
                    if sent_count % 100 == 0:
                        current_real_time = time.time() - start_time
                        current_log_time = (timestamp - first_log_time) / 1000000.0

                        print(f"Enviadas: {sent_count:5d}, "
                              f"Tempo real: {current_real_time:6.1f}s, "
                              f"Tempo log: {current_log_time:6.1f}s, "
                              f"Velocidade: {self.speed_factor:.2f}x, "
                              f"ID: {msg_id:08X}")
                else:
                    error_count += 1
                    if error_count > 10:
                        print(f"Muitos erros de envio ({error_count}). Verificar conexão.")

        except KeyboardInterrupt:
            print("\nInterrompido pelo usuário")
        except Exception as e:
            print(f"Erro durante reprodução: {e}")
        finally:
            # Sinaliza fim da reprodução
            if self.serial_conn:
                try:
                    self.serial_conn.write(b"END\n")
                    time.sleep(0.1)
                    self.serial_conn.close()
                except:
                    pass
                print("Conexão serial fechada")

            print(f"\nResumo:")
            print(f"Mensagens enviadas: {sent_count}")
            print(f"Erros: {error_count}")

def signal_handler(sig, frame):
    """Handler para interrupção por Ctrl+C"""
    global replayer
    print('\nInterrompendo...')
    if replayer:
        replayer.running = False
    sys.exit(0)

if __name__ == "__main__":
    # Configuração do handler de sinal
    replayer = None
    signal.signal(signal.SIGINT, signal_handler)

    # Parâmetros configuráveis
    LOG_FILE = "data/log.csv"
    SERIAL_PORT = "/dev/ttyACM1"
    INITIAL_SPEED = 1.0

    # Cria e executa o reprodutor
    replayer = CanLogReplayer(port=SERIAL_PORT, speed_factor=INITIAL_SPEED)
    replayer.replay_log(LOG_FILE)