# AI Factory - System Design Document

## 1. Overview

### Problem Statement

Hiện nay việc xây dựng một hệ thống AI hoặc Automation vẫn đòi hỏi người dùng phải có kiến thức về:

* Workflow Design
* API Integration
* Agent Architecture
* Database
* Deployment
* Infrastructure

Người dùng thường biết mình muốn giải quyết vấn đề gì nhưng không biết cách triển khai thành một hệ thống thực tế.

Ví dụ:

> Tôi muốn theo dõi các paper AI mới mỗi ngày và nhận báo cáo tóm tắt qua Notion.

> Tôi muốn xây chatbot nội bộ cho công ty.

> Tôi muốn theo dõi giá vàng, tỷ giá USD và gửi cảnh báo khi có biến động bất thường.

Để triển khai các bài toán trên, người dùng thường phải trải qua quá trình nghiên cứu công nghệ, thiết kế workflow, lựa chọn công cụ và lập trình hệ thống.

---

### Solution

AI Factory là một hệ thống chuyển đổi yêu cầu bằng ngôn ngữ tự nhiên thành một hệ thống automation có thể triển khai được.

Người dùng chỉ cần mô tả:

```text
Tôi muốn làm gì?
```

AI Factory sẽ tự động:

* Phân tích yêu cầu
* Thiết kế workflow
* Lựa chọn công nghệ
* Đề xuất kiến trúc hệ thống
* Sinh mã nguồn
* Sinh cấu hình triển khai

---

## 2. Product Vision

### Traditional Process

```text
Idea
 ↓
Research
 ↓
Learn Tools
 ↓
Design Workflow
 ↓
Write Code
 ↓
Deploy
```

### AI Factory Process

```text
Idea
 ↓
AI Factory
 ↓
Workflow
 ↓
Source Code
 ↓
Deployment
```

Mục tiêu là giảm thời gian từ ý tưởng đến sản phẩm từ nhiều ngày xuống vài phút.

---

## 3. Core Value Proposition

AI Factory không phải là một Agent Builder.

AI Factory là:

> Business Problem → Deployable Automation System

Đầu ra không chỉ là agent.

Đầu ra bao gồm:

* Workflow Diagram
* System Architecture
* Agent Architecture
* Database Schema
* API Design
* Source Code
* Docker Deployment
* Monitoring Configuration

---

## 4. System Architecture

### High Level Architecture

```text
User Request
      │
      ▼
Intent Analysis Engine
      │
      ▼
Task Decomposition Engine
      │
      ▼
Workflow Synthesis Engine
      │
      ▼
Technology Selection Engine
      │
      ▼
Code Generation Engine
      │
      ▼
Deployment Generator
      │
      ▼
Output Package
```

---

## 5. Functional Components

### 5.1 Intent Analysis Engine

Nhiệm vụ:

* Xác định domain
* Xác định objective
* Xác định input/output

Ví dụ:

Input:

```text
Theo dõi giá vàng mỗi ngày và gửi cảnh báo.
```

Output:

```json
{
  "domain": "finance",
  "objective": [
    "monitor",
    "detect anomaly",
    "notify"
  ]
}
```

---

### 5.2 Task Decomposition Engine

Chuyển đổi mục tiêu thành các nhiệm vụ nhỏ hơn.

Ví dụ:

```text
Monitor Gold Price
```

↓

```text
Collect Data
Store Data
Analyze Trend
Detect Anomaly
Send Notification
```

---

### 5.3 Workflow Synthesis Engine

Sinh workflow thực thi.

Ví dụ:

```text
Scheduler
 ↓
Data Collector
 ↓
Database
 ↓
Analyzer
 ↓
Notifier
```

Workflow được lưu dưới dạng JSON.

Ví dụ:

```json
{
  "workflow": [
    "scheduler",
    "collector",
    "database",
    "analyzer",
    "notifier"
  ]
}
```

---

### 5.4 Technology Selection Engine

Tự động lựa chọn công nghệ phù hợp.

Ví dụ:

| Requirement  | Selected Technology |
| ------------ | ------------------- |
| Storage      | PostgreSQL          |
| Search       | Elasticsearch       |
| LLM          | GPT                 |
| Deployment   | Docker              |
| Notification | Telegram            |

---

### 5.5 Agent Planning Engine

Chỉ tạo Agent khi workflow yêu cầu.

Ví dụ:

Research Workflow:

```text
Web Search
 ↓
Research Agent
 ↓
Fact Check Agent
 ↓
Report Agent
```

Simple Workflow:

```text
Email
 ↓
Google Drive
```

Không cần Agent.

---

### 5.6 Code Generation Engine

Sinh:

```text
project/
├── agents/
├── tools/
├── workflow/
├── config/
├── Dockerfile
└── docker-compose.yml
```

Đầu ra là source code skeleton có thể chỉnh sửa hoặc chạy trực tiếp.

---

### 5.7 Deployment Generator

Sinh:

* Dockerfile
* docker-compose.yml
* Environment Variables
* Deployment Guide

Ví dụ:

```bash
docker compose up
```

---

## 6. Workflow Example

### User Request

```text
Theo dõi giá vàng, USD/VND và lãi suất.
Nếu có biến động bất thường thì gửi Telegram.
```

---

### Generated Workflow

```text
Scheduler
 ↓
Economic Data Collector
 ↓
Database
 ↓
Trend Analysis
 ↓
Anomaly Detection
 ↓
Report Generator
 ↓
Telegram Bot
```

---

### Generated Components

#### Agent 1

Data Collector

Responsibilities:

* Collect Gold Price
* Collect Exchange Rate
* Collect Interest Rate

#### Agent 2

Trend Analyzer

Responsibilities:

* Trend Detection
* Time Series Analysis

#### Agent 3

Alert Agent

Responsibilities:

* Threshold Monitoring
* Alert Generation

#### Agent 4

Report Generator

Responsibilities:

* Report Writing
* Economic Summary

---

## 7. Outputs

AI Factory sinh ra:

### Design Artifacts

* Workflow Diagram
* System Architecture
* Agent Architecture
* Database Schema

### Engineering Artifacts

* Source Code Skeleton
* API Definition
* Docker Configuration

### Deployment Artifacts

* Deployment Guide
* Environment Variables
* Monitoring Setup

---

## 8. Evaluation Metrics

### Cost

Ước lượng chi phí vận hành.

Ví dụ:

```text
$2 / month
```

---

### Latency

Thời gian thực thi workflow.

Ví dụ:

```text
10 seconds
```

---

### Reliability

Đánh giá độ ổn định của hệ thống.

Ví dụ:

```text
High
```

---

### Maintainability

Đánh giá khả năng bảo trì.

Ví dụ:

```text
Low Maintenance
```

↓

Monitoring Dashboard

---

## 9. Conclusion

AI Factory là nền tảng chuyển đổi yêu cầu kinh doanh thành hệ thống automation có thể triển khai.

Người dùng không cần hiểu:

* Workflow Design
* Agent Architecture
* Infrastructure
* API Integration

Người dùng chỉ cần mô tả:

> Tôi muốn giải quyết vấn đề gì?

AI Factory sẽ tự động sinh:

* Workflow
* Architecture
* Agent Plan
* Source Code
* Deployment Configuration

Giúp rút ngắn đáng kể khoảng cách giữa ý tưởng và hệ thống vận hành thực tế.
