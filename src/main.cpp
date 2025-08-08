#include <esp32_can.h>

CAN_FRAME txFrame;

void setup()
{
    Serial.begin(115200);

    Serial.println("Initializing ...");

    CAN0.setCANPins(GPIO_NUM_21, GPIO_NUM_2);
    CAN0.begin(500000);

    Serial.println("Ready ...!");
    CAN_FRAME txFrame;
    txFrame.rtr = 0;
    txFrame.id = 0x090;
    txFrame.extended = false;
    txFrame.length = 4;
    txFrame.data.uint8[0] = 0x10;
    txFrame.data.uint8[1] = 0x1A;
    txFrame.data.uint8[2] = 0xFF;
    txFrame.data.uint8[3] = 0x5D;
    CAN0.sendFrame(txFrame);
}

void loop()
{
    byte i = 0;
    txFrame.id += 10;
    txFrame.length = 8;
    for (i = 0; i < txFrame.length; i++) {
        txFrame.data.uint8[i]++;
    }
    Serial.print("Enviando frame:");
    Serial.println(txFrame.id);
    CAN0.sendFrame(txFrame);
    delay(100);
}
