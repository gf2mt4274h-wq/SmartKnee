#include <HardwareSerial.h>

// ==========================================
// ⚠️ 请根据你的板子丝印修改这里的引脚定义！
// 常见 S3-N16R8 (DevKitC-1): TX=43, RX=44
// 某些 S3-Nano:              TX=17, RX=18
// ==========================================
#define UART_TX_PIN 43
#define UART_RX_PIN 44

#define LED_PIN 2       // 大多数 S3 板载 LED 在 GPIO2 或 GPIO48
#define BAUD_RATE 115200

// 创建 UART0 实例
HardwareSerial MySerial(0); 

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // 1. 初始化 USB CDC (Serial)
  Serial.begin(BAUD_RATE);
  delay(2000); // 等待 macOS/Windows 枚举 USB
  
  while (!Serial) {
    delay(10);
  }
  
  Serial.println("========================================");
  Serial.println("ESP32-S3-N16R8 UART Loopback Test");
  Serial.printf("Config: TX=GPIO%d, RX=GPIO%d\n", UART_TX_PIN, UART_RX_PIN);
  Serial.println("========================================");

  // 2. 初始化硬件 UART0
  // 参数: begin(baud, config, rxPin, txPin)
  MySerial.begin(BAUD_RATE, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);
  
  Serial.println("UART0 Initialized.");
  Serial.println("Please short TX and RX pins with a jumper wire.");
  Serial.println("Type 'hello' in the monitor to test.");
  Serial.println("========================================");
  
  digitalWrite(LED_PIN, HIGH); // LED 常亮表示就绪
}

void loop() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    
    if (input.length() > 0) {
      Serial.printf("[USB] Sending: '%s'\n", input.c_str());
      
      // 发送数据到 UART0
      MySerial.println(input);
      
      // 等待数据回传 (自环应该瞬间完成，给一点余量)
      delay(20); 
      
      // 检查是否有数据回来
      if (MySerial.available()) {
        String response = MySerial.readStringUntil('\n');
        response.trim();
        
        Serial.printf("[UART] Received: '%s'\n", response.c_str());
        
        if (response.equalsIgnoreCase(input)) {
          Serial.println("✅ SUCCESS: Loopback works! Pin definition is correct.");
          digitalWrite(LED_PIN, HIGH);
        } else {
          Serial.println("❌ FAIL: Data mismatch. Check wiring or baud rate.");
          digitalWrite(LED_PIN, LOW);
        }
      } else {
        Serial.println("❌ FAIL: No data received. Check if TX/RX are shorted correctly.");
        Serial.println("   -> Are you sure about GPIO" + String(UART_TX_PIN) + " and GPIO" + String(UART_RX_PIN) + "?");
        digitalWrite(LED_PIN, LOW);
      }
    }
  }
}
