#include <esp32_can.h>

CAN_FRAME txFrame;

void setup()
{
    Serial.begin(115200);
    delay(1000);

    Serial.println("============ CAN SENDER - ESP32-C6 ============");

    CAN0.setCANPins(GPIO_NUM_21, GPIO_NUM_2);
    CAN0.begin(500000);

    Serial.println("CAN inicializado! Aguardando dados via Serial...");
    Serial.println("Formato: timestamp,id,dlc,data0,data1,data2...");
}

void loop()
{
    if (Serial.available()) {
        String line = Serial.readStringUntil('\n');
        line.trim();

        if (line == "END") {
            Serial.println("Reprodução finalizada!");
            return;
        }

        // Parse da linha: timestamp,id,dlc,data0,data1,...
        int commaCount = 0;
        int positions[20];

        // Encontrar vírgulas
        for (int i = 0; i < line.length(); i++) {
            if (line.charAt(i) == ',') {
                positions[commaCount++] = i;
            }
        }

        if (commaCount >= 2) {
            // Extrair timestamp (não usado aqui, o Python controla o timing)
            // String timestampStr = line.substring(0, positions[0]);

            // Extrair ID
            String idStr = line.substring(positions[0] + 1, positions[1]);
            uint32_t id = strtoul(idStr.c_str(), NULL, 16);

            // Extrair DLC
            String dlcStr = line.substring(positions[1] + 1, positions[2]);
            uint8_t dlc = dlcStr.toInt();
            if (dlc > 8) dlc = 8;

            // Extrair dados
            uint8_t data[8] = {0};
            for (int i = 0; i < dlc && (i + 3) <= commaCount; i++) {
                int start = positions[i + 2] + 1;
                int end = (i + 3 < commaCount) ? positions[i + 3] : line.length();

                String dataStr = line.substring(start, end);
                data[i] = strtoul(dataStr.c_str(), NULL, 16);
            }

            // Enviar frame CAN
            CAN_FRAME frame;
            frame.id = id;
            frame.length = dlc;
            frame.extended = (id > 0x7FF);
            frame.rtr = 0;

            for (int i = 0; i < dlc; i++) {
                frame.data.uint8[i] = data[i];
            }

            Can0.sendFrame(frame);

            // Confirmar envio
            Serial.println("OK");
        }
    }
}
