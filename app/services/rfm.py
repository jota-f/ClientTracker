from datetime import datetime, timezone, timedelta

def calculate_rfm_score(last_contact: datetime, sales_potential: int, engagement: int = 0) -> dict:
    """
    Calcula o score RFM (Recency, Potential, Engagement) para um cliente.
    
    Recência (R):
    - Menos de 1 mês = 5 pontos
    - 1-3 meses = 3 pontos
    - Mais de 3 meses = 1 ponto
    
    Potencial (P):
    - Alto (5) = 5 pontos
    - Médio (3) = 3 pontos
    - Baixo (1) = 1 ponto
    
    Engajamento (E):
    - Mais de 5 interações = 5 pontos
    - 3-4 interações = 3 pontos
    - 1-2 interações = 1 ponto
    - 0 interações = 0 pontos
    """
    now = datetime.now(timezone.utc)
    
    # Garantir que last_contact seja timezone-aware
    if last_contact.tzinfo is None:
        last_contact = last_contact.replace(tzinfo=timezone.utc)
    
    # Calcular recency (meses desde último contato)
    months_since_contact = (now - last_contact).days / 30
    
    # Score de recency
    if months_since_contact < 1:  # Menos de 1 mês
        recency_score = 5
    elif months_since_contact <= 3:  # 1-3 meses
        recency_score = 3
    else:  # Mais de 3 meses
        recency_score = 1
    
    # Score de potencial
    if sales_potential >= 5:  # Alto
        potential_score = 5
    elif sales_potential >= 3:  # Médio
        potential_score = 3
    else:  # Baixo
        potential_score = 1
    
    # Score de engagement baseado no número de interações
    # Garantir que engagement é no mínimo 0
    engagement = max(0, engagement)
    
    if engagement > 5:
        engagement_score = 5
    elif engagement >= 3:
        engagement_score = 3
    elif engagement >= 1:
        engagement_score = 1
    else:
        engagement_score = 0
    
    # Calcular score total
    total_score = recency_score + potential_score + engagement_score
    
    return {
        "recency": recency_score,
        "potential": potential_score,
        "engagement": engagement_score,
        "total": total_score
    } 