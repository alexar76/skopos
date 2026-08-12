# เอกสาร SKOPOS

ยินดีต้อนรับสู่คู่มือผู้ปฏิบัติการ SKOPOS ใช้แท็บด้านบนเพื่อสลับระหว่างการตั้งค่า การ deploy การกำหนดค่า และการใช้งานประจำวัน

## SKOPOS ทำอะไร

SKOPOS รวบรวม **nginx access log** จากเซิร์ฟเวอร์ผ่าน SSH เก็บใน SQLite หรือ PostgreSQL ในเครื่อง และแสดงการวิเคราะห์พร้อมศูนย์ความปลอดภัยและรายงานที่มี AI ช่วย

## ลิงก์ด่วน

| งาน | ตำแหน่ง |
|------|--------|
| ตั้งค่าครั้งแรก | **เริ่มต้นด่วน** ในแถบด้านข้างหรือแถบบน |
| SSH และ log | **การตั้งค่า** → `servers.yaml` |
| แดชบอร์ดทราฟฟิก | **การวิเคราะห์** (หน้าแรก) |
| สแกนความปลอดภัย | **ความปลอดภัย** |
| เอเจนต์ AI | ปุ่มแชทลอย (มุมล่างขวา) |

## Pages at a glance

| งาน | ตำแหน่ง |
|------|--------|
| **Quick Start** | Six-step wizard — server, SSH, password, collect, scan |
| **Analytics** | Traffic dashboards, AI briefing, 7 tabs (Overview → System) |
| **Security** | 9 tabs — score, AI report, ports, knocks, 3D map, audit |
| **Scan History** | Timeline, trends, compare two scans, log table |
| **Settings** | Password, DB, auto-scan, Telegram, SSH keys, fleet YAML |
| **Documentation** | This guide — 20 languages, embedded screenshots |

> Open **Documentation** in the sidebar for the full operator guide with screenshots. The **Usage** tab documents every page and tab in detail.

## ภาพหน้าจอ

![แดชบอร์ดการวิเคราะห์ — ธีมพรีเมียม](../../screenshots/analytics-premium.png)

![การนำทางแถบด้านข้างและตัวเลือกธีม](../../screenshots/sidebar-nav.png)

> **หมายเหตุ:** ภาพหน้าจอแสดง UI ข้อมูล fleet ของคุณจะต่างกัน
