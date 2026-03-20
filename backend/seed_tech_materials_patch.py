"""
브라우저 크롤링 결과로 기존 LINK/약한 레코드를 MARKDOWN으로 보강 + Flask 추가
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reboot_api.settings')
django.setup()

import requests, html2text
from bs4 import BeautifulSoup
from learning.models import LectureMaterial
from users.models import User

uploader = User.objects.filter(role='INSTRUCTOR').first() or User.objects.filter(username='admin').first()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36',
}
converter = html2text.HTML2Text()
converter.ignore_links = False
converter.ignore_images = True
converter.body_width = 0

def fetch_md(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        for t in soup.find_all(['nav','footer','header','script','style','aside','noscript','iframe']): t.decompose()
        main = soup.find('main') or soup.find('article') or soup.find('body') or soup
        md = converter.handle(str(main)).strip()
        return md if len(md) > 100 else None
    except:
        return None

# ─── 1. 기존 레코드 보강 (브라우저 크롤링 결과 반영) ───

UPDATES = {
    "[프론트엔드] Nuxt.js 공식 문서": """# 출처: https://nuxt.com/docs

---

# Nuxt.js 공식 문서

## Introduction
Nuxt is an open-source framework for building type-safe, performant, and production-grade full-stack web applications with Vue.js. It features hot module replacement in development and server-side rendering (SSR) by default.

## Key Features

### Automation & Conventions
- **File-based routing**: Define routes based on the `pages/` directory structure. No need for manual configuration.
- **Code splitting**: Nuxt automatically splits your code into smaller chunks, reducing initial load time.
- **Auto-imports**: Use Vue composables and components without explicit `import` statements.
- **Zero-config TypeScript**: Full TypeScript support out of the box without additional configuration.

### Server-Side Rendering (SSR)
Built-in SSR capabilities provide:
- Faster initial page loads
- Improved SEO (search engine optimization)
- Better accessibility
- Easier caching strategies

### Server Engine (Nitro)
Nuxt's server engine generates a light output compatible with multiple deployment targets:
- **Node.js**: Traditional server deployments
- **Serverless**: AWS Lambda, Netlify Functions, Vercel
- **Edge**: Cloudflare Workers, Deno Deploy
- **Static**: Pre-rendered static site generation (SSG)

### Modular Architecture
- Highly extensible through a robust module system
- Core packages: `@nuxt/kit` for module development, `nitro` for server engine
- Rich ecosystem of community modules for authentication, CMS, SEO, analytics, and more

## Architecture
Nuxt is composed of:
- **Nitro** (server engine)
- **Vite** or **Webpack** (bundlers)
- **h3** (HTTP framework)
- **unjs** ecosystem (universal JavaScript utilities)
- **Nuxt Core** (orchestration layer)

## Getting Started
```bash
npx nuxi@latest init my-nuxt-app
cd my-nuxt-app
npm install
npm run dev
```

## Directory Structure
```
my-nuxt-app/
├── pages/         # File-based routing
├── components/    # Auto-imported Vue components
├── composables/   # Auto-imported composables
├── layouts/       # Page layouts
├── middleware/     # Route middleware
├── plugins/       # Vue plugins
├── server/        # Server API routes (Nitro)
├── public/        # Static assets
├── app.vue        # Root component
└── nuxt.config.ts # Configuration
```
""",

    "[백엔드] NestJS 공식 문서": """# 출처: https://docs.nestjs.com/

---

# NestJS 공식 문서

## Introduction
Nest (NestJS) is a framework for building efficient, scalable Node.js server-side applications. It uses progressive JavaScript, is built with and fully supports TypeScript, and combines elements of OOP (Object-Oriented Programming), FP (Functional Programming), and FRP (Functional Reactive Programming).

## Philosophy
Nest provides an out-of-the-box application architecture heavily inspired by Angular. It allows developers to create highly testable, scalable, loosely coupled, and easily maintainable applications. The architecture solves the main problem of — **Architecture**.

## Under the Hood
- **Default HTTP Platform**: Express (most widely used Node.js HTTP framework)
- **Alternative**: Fastify (for high-performance scenarios)
- Nest provides a level of abstraction above these common Node.js frameworks but also exposes their APIs directly to the developer

## Installation
```bash
$ npm i -g @nestjs/cli
$ nest new project-name
```

## Core Concepts

### Controllers
Controllers are responsible for handling incoming requests and returning responses.
```typescript
@Controller('cats')
export class CatsController {
  @Get()
  findAll(): string {
    return 'This action returns all cats';
  }
}
```

### Providers (Services)
Providers handle business logic and can be injected into controllers via Dependency Injection.
```typescript
@Injectable()
export class CatsService {
  private readonly cats: Cat[] = [];

  findAll(): Cat[] {
    return this.cats;
  }
}
```

### Modules
Modules organize the application structure. Each app has at least one root module.
```typescript
@Module({
  controllers: [CatsController],
  providers: [CatsService],
})
export class CatsModule {}
```

### Middleware
Functions called before route handlers. Can perform tasks like logging, authentication.

### Guards
Determine whether a request will be handled, used for authorization.

### Interceptors
Bind extra logic before/after method execution, transform results, extend behavior.

### Pipes
Transform and validate input data.

## Key Features
- First-class TypeScript support
- Dependency Injection (IoC container)
- Modular architecture
- Platform agnostic (Express / Fastify)
- Built-in support for WebSockets, GraphQL, Microservices
- REST API, gRPC, MQTT support
- Testing utilities (unit + e2e)
- CLI for scaffolding and code generation
""",

    "[DB] MySQL 공식 문서": """# 출처: https://dev.mysql.com/doc/

---

# MySQL 공식 문서

## Overview
MySQL is the world's most popular open-source relational database management system (RDBMS). It is a fast, multithreaded, multi-user, and robust SQL database server. MySQL is Dual Licensed (GPL for open source or commercial license from Oracle).

## MySQL HeatWave
- OLTP MySQL cloud service built on MySQL Enterprise Edition
- Integrated generative AI with MySQL HeatWave GenAI
- Accelerated query performance with MySQL HeatWave
- Query data in object storage and MySQL with MySQL HeatWave Lakehouse
- Automated machine learning pipeline with MySQL HeatWave AutoML

## Cloud Deployment
- MySQL HeatWave on OCI, AWS, and Azure
- MySQL on OCI Marketplace
- Cloud-native deployment options

## Enterprise Features
- **Backup**: MySQL Enterprise Backup for hot backups
- **Security**: Enterprise Authentication, Encryption, Audit, Firewall
- **Thread Pool**: Connection pooling for high concurrency
- **Data Masking**: Privacy compliance features
- **Monitoring**: Oracle Enterprise Manager integration

## High Availability & Replication
- **InnoDB Cluster**: Built-in HA solution using Group Replication
- **InnoDB ClusterSet**: Multi-datacenter HA
- **InnoDB ReplicaSet**: Simplified async replication management
- **Group Replication**: Multi-primary or single-primary modes
- **MySQL Router**: Lightweight middleware for routing and load balancing
- **MySQL Operator for Kubernetes**: Cloud-native orchestration

## Server & Cluster
- MySQL 8.0/8.4 Reference Manual
- MySQL Cluster (NDB) for distributed computing
- NDB Cluster API Developer Guide
- Error Reference and Version Reference

## Tools & Utilities
- **MySQL Workbench**: Visual database design and administration
- **MySQL Shell**: Advanced client and code editor (SQL, Python, JavaScript)
- **MySQL Shell for VS Code**: IDE integration
- **MySQL Router**: Connection routing and load balancing

## Connectors & APIs
- Connector/J (Java/JDBC)
- Connector/ODBC
- Connector/NET (C#/.NET)
- Connector/Python
- Connector/C++ 
- Connector/Node.js
- MySQL C API
- X DevAPI (document store + relational)

## SQL Language Features
- Comprehensive SQL implementation
- Stored Procedures, Functions, Triggers
- Views, Indexes, Partitioning
- JSON support and Document Store
- Full-text search
- Spatial data (GIS)
- Window functions (8.0+)
- Common Table Expressions (CTEs)
""",

    "[클라우드] AWS 공식 문서": """# 출처: https://docs.aws.amazon.com/

---

# AWS (Amazon Web Services) 공식 문서

## What is AWS?
Amazon Web Services (AWS) offers over 200 fully featured global cloud-based products including compute, storage, databases, analytics, networking, mobile, developer tools, management tools, IoT, security, and enterprise applications.

## Core Advantages
- **Cost Savings**: Replace upfront capital infrastructure expenses with low variable costs that scale
- **Speed & Agility**: Provision resources in minutes, not weeks
- **Global Reach**: Deploy in multiple AWS Regions worldwide
- **Elasticity**: Scale up or down automatically based on demand

## Key Services (332 products across 32 categories)

### Compute
- **EC2**: Virtual servers in the cloud (IaaS)
- **Lambda**: Serverless compute (FaaS) — run code without managing servers
- **ECS/EKS**: Container orchestration (Docker/Kubernetes)
- **Fargate**: Serverless containers
- **Elastic Beanstalk**: PaaS for web applications

### Storage
- **S3**: Object storage with 99.999999999% durability
- **EBS**: Block storage for EC2 instances
- **EFS**: Managed NFS file system
- **Glacier**: Long-term archival storage

### Database
- **RDS**: Managed relational databases (MySQL, PostgreSQL, Oracle, SQL Server)
- **DynamoDB**: Fully managed NoSQL database
- **Aurora**: MySQL/PostgreSQL-compatible high-performance DB
- **ElastiCache**: In-memory caching (Redis/Memcached)
- **DocumentDB**: MongoDB-compatible document database

### Networking
- **VPC**: Isolated virtual network
- **CloudFront**: CDN for content delivery
- **Route 53**: DNS and domain management
- **API Gateway**: RESTful and WebSocket APIs
- **ELB**: Load balancing (ALB, NLB, CLB)

### Machine Learning & AI
- **SageMaker**: End-to-end ML platform
- **Rekognition**: Image/video analysis
- **Comprehend**: NLP service
- **Bedrock**: Generative AI with foundation models

### Security & Identity
- **IAM**: Identity and Access Management
- **Cognito**: User authentication for apps
- **KMS**: Key Management Service
- **WAF**: Web Application Firewall
- **Shield**: DDoS protection

### Developer Tools
- **CodePipeline**: CI/CD pipeline
- **CodeBuild**: Build service
- **CodeDeploy**: Deployment automation
- **Cloud9**: Cloud-based IDE

## SDKs & Toolkits
AWS CLI, SDKs for C++, Go, Java, JavaScript, Kotlin, .NET, PHP, Python, Ruby, Rust, Swift
""",

    "[프론트엔드] Svelte 공식 문서": """# 출처: https://svelte.dev/docs/svelte/overview

---

# Svelte 공식 문서

## Introduction
Svelte is a framework for building user interfaces on the web. It uses a compiler to turn declarative components written in HTML, CSS, and JavaScript into lean, tightly optimized JavaScript.

## Core Concept: Compiler-based
Unlike traditional frameworks (React, Vue) that do the work in the browser using techniques like virtual DOM diffing, Svelte shifts that work into a **compile step** that happens when you build your app. Instead of applying diffs at runtime, Svelte writes code that surgically updates the DOM when the state of your application changes.

## Component Structure
A Svelte component is a `.svelte` file containing three sections:
```svelte
<script lang="ts">
  // Logic (JavaScript/TypeScript)
  let count = $state(0);
  
  function increment() {
    count++;
  }
</script>

<!-- Template (HTML) -->
<button onclick={increment}>
  Clicks: {count}
</button>

<!-- Styles (scoped CSS) -->
<style>
  button {
    font-size: 2em;
    background: #ff3e00;
    color: white;
    border: none;
    padding: 0.5em 1em;
    border-radius: 4px;
  }
</style>
```

## Runes (Svelte 5+ Reactivity System)
Svelte 5 introduces **Runes** — a new, explicit reactivity system:
- **`$state`**: Declare reactive state variables
- **`$derived`**: Computed values that auto-update when dependencies change
- **`$effect`**: Side effects that run when dependencies change
- **`$props`**: Declare component props

```svelte
<script>
  let count = $state(0);
  let doubled = $derived(count * 2);
  
  $effect(() => {
    console.log(`count is ${count}`);
  });
</script>
```

## Template Syntax
HTML-based markup with logic blocks:
- **`{#if ...}`**: Conditional rendering
- **`{#each ...}`**: List iteration
- **`{#await ...}`**: Promise handling
- **`{@html ...}`**: Raw HTML insertion
- **`{@render ...}`**: Snippet rendering
- **Bindings**: `bind:value`, `bind:checked`, etc.

## Styling
- **Scoped CSS**: Styles are component-scoped by default
- **Global styles**: Use `:global()` selector
- **Custom properties**: CSS variables with `--var-name`
- **Transitions**: Built-in `transition:`, `in:`, `out:` directives
- **Animations**: `animate:` directive for list reordering

## Built-in Features
- **Transitions & Animations**: `fade`, `fly`, `slide`, `scale`, `draw`, `crossfade`
- **Stores**: Writable, readable, derived stores for shared state
- **Context API**: `setContext` / `getContext` for component tree communication
- **Actions**: `use:action` for reusable DOM element behavior
- **Special Elements**: `<svelte:head>`, `<svelte:window>`, `<svelte:body>`, `<svelte:component>`

## SvelteKit (Companion Framework)
Full-stack application framework powered by Vite:
- **File-based routing** (`routes/` directory)
- **Server-side rendering (SSR)**
- **Static site generation (SSG)**
- **API routes** (`+server.js`)
- **Form actions** for progressive enhancement
- **Adapters** for various deployment targets

## Getting Started
```bash
npx sv create myapp
cd myapp
npm install
npm run dev
```

## Editor Tooling
- VS Code extension (Svelte for VS Code)
- IntelliJ plugin
- Language server protocol (LSP) support
""",
}

# 기존 레코드 업데이트
for title, content in UPDATES.items():
    try:
        mat = LectureMaterial.objects.get(title=title)
        mat.content_type = "MARKDOWN"
        mat.content_data = content
        mat.file_type = "MD"
        mat.save()
        print(f"  ✅ 보강 완료: {title} ({len(content)/1024:.1f}KB)")
    except LectureMaterial.DoesNotExist:
        print(f"  ❌ 레코드 없음: {title}")

# ─── 2. Flask 추가 크롤링 ───
flask_title = "[백엔드] Flask 공식 문서"
if not LectureMaterial.objects.filter(title=flask_title).exists():
    urls = [
        "https://flask.palletsprojects.com/en/stable/",
        "https://flask.palletsprojects.com/en/stable/quickstart/",
    ]
    combined = ""
    for url in urls:
        md = fetch_md(url)
        if md:
            combined += f"\n\n# 출처: {url}\n\n---\n\n{md}\n"
    
    if not combined.strip():
        # fallback 내용
        combined = """# 출처: https://flask.palletsprojects.com/

---

# Flask 공식 문서

## Overview
Flask is a lightweight WSGI web application framework for Python. It is designed to make getting started quick and easy, with the ability to scale up to complex applications.

## Key Features
- **Lightweight & Flexible**: Micro-framework with no database abstraction layer or form validation built-in
- **Jinja2 Templating**: Powerful template engine for HTML generation
- **Werkzeug WSGI Toolkit**: Robust request/response handling
- **Built-in Development Server**: With debugger and hot reloading
- **RESTful Request Dispatching**: Clean URL routing
- **Unit Testing Support**: Integrated test client
- **Extensions**: Rich ecosystem (Flask-SQLAlchemy, Flask-Login, Flask-WTF, Flask-RESTful, etc.)

## Quick Start
```python
from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello():
    return 'Hello, World!'

if __name__ == '__main__':
    app.run(debug=True)
```

## Installation
```bash
pip install Flask
```

## Core Concepts
- **Routing**: `@app.route()` decorator for URL mapping
- **Templates**: Jinja2 template rendering with `render_template()`
- **Request/Response**: `request` object for incoming data, `make_response()` for responses
- **Sessions**: Secure client-side sessions
- **Blueprints**: Modular application components
- **Error Handling**: Custom error pages with `@app.errorhandler()`
- **Logging**: Built-in logging integration
- **Configuration**: Multiple config loading strategies (env, files, objects)

## Flask vs Django
| Feature | Flask | Django |
|---------|-------|--------|
| Type | Micro-framework | Full-stack framework |
| ORM | None (use SQLAlchemy) | Built-in Django ORM |
| Admin | None | Built-in admin panel |
| Philosophy | Choose your tools | Batteries included |
| Best For | APIs, microservices | Large web applications |
"""
    
    LectureMaterial.objects.create(
        lecture=None,
        title=flask_title,
        content_type="MARKDOWN",
        content_data=combined,
        file_type="MD",
        uploaded_by=uploader,
    )
    print(f"  ✅ Flask 추가 완료 ({len(combined)/1024:.1f}KB)")
else:
    print(f"  ⏭️  Flask 이미 존재")

# ─── 결과 출력 ───
print(f"\n{'='*60}")
total = LectureMaterial.objects.count()
md_count = LectureMaterial.objects.filter(content_type='MARKDOWN').count()
link_count = LectureMaterial.objects.filter(content_type='LINK').count()
print(f" [결과] 총 레코드: {total}건 (MARKDOWN: {md_count}건, LINK: {link_count}건)")
print(f"{'='*60}")
