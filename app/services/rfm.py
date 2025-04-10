from datetime import datetime, timezone, timedelta

def calculate_rfm_score(last_contact: datetime, sales_potential: int, interactions: list = None) -> dict:
    """
    Calcula o score RFM (Recency, Potential, Engagement) para um cliente.
    
    Recência (R):
    - Menos de 15 dias = 5 pontos
    - 15 dias a 1 mês = 4 pontos
    - 1-3 meses = 3 pontos
    - 3-6 meses = 2 pontos
    - Mais de 6 meses = 0 ponto
    
    Potencial (P):
    - Alto (5) = 5 pontos
    - Médio (3) = 3 pontos
    - Baixo (1) = 1 ponto
    
    Engajamento (E):
    Considera o número de interações e sua recência:
    - Interações nos últimos 30 dias = peso 1.0
    - Interações de 1-3 meses = peso 0.8
    - Interações de 3-6 meses = peso 0.5
    - Interações mais antigas que 6 meses = não contam
    
    Score final de engajamento:
    - Mais de 5 interações ponderadas = 5 pontos
    - 3-5 interações ponderadas = 3 pontos
    - 1-2 interações ponderadas = 1 ponto
    - 0 interações = 0 pontos
    """
    now = datetime.now(timezone.utc)
    
    # Garantir que last_contact seja timezone-aware
    if last_contact.tzinfo is None:
        last_contact = last_contact.replace(tzinfo=timezone.utc)
    
    # Calcular recency (meses desde último contato)
    months_since_contact = (now - last_contact).days / 30
    
    # Score de recency
    if months_since_contact < 0.5:  # Menos de 15 dias
        recency_score = 5
    elif months_since_contact < 1:   # Menos de 1 mês
        recency_score = 4
    elif months_since_contact <= 3:  # 1-3 meses
        recency_score = 3
    elif months_since_contact <= 6:  # 3-6 meses
        recency_score = 2
    else:  # Mais de 6 meses
        recency_score = 0
    
    # Score de potencial
    if sales_potential >= 5:  # Alto
        potential_score = 5
    elif sales_potential >= 3:  # Médio
        potential_score = 3
    else:  # Baixo
        potential_score = 1
    
    # Score de engagement baseado no número e recência das interações
    weighted_interactions = 0
    
    if interactions:
        for interaction in interactions:
            # Adaptação para suportar tanto dicionários quanto objetos Interaction
            if hasattr(interaction, 'date'):
                interaction_date = interaction.date
            else:
                interaction_date = interaction.get('date', None)
                
            if interaction_date:
                if isinstance(interaction_date, str):
                    try:
                        interaction_date = datetime.fromisoformat(interaction_date.replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        continue
                
                # Garantir que interaction_date seja timezone-aware
                if interaction_date.tzinfo is None:
                    interaction_date = interaction_date.replace(tzinfo=timezone.utc)
                
                months_since_interaction = (now - interaction_date).days / 30
                
                # Aplicar peso baseado na idade da interação
                # Interações mais antigas que 6 meses não contam
                if months_since_interaction <= 1:  # Último mês
                    weighted_interactions += 1.0
                elif months_since_interaction <= 3:  # 1-3 meses
                    weighted_interactions += 0.8
                elif months_since_interaction <= 6:  # 3-6 meses
                    weighted_interactions += 0.5
                # Interações mais antigas que 6 meses não somam pontos
    
    # Calcular score de engagement baseado nas interações ponderadas
    if weighted_interactions > 5:
        engagement_score = 5
    elif weighted_interactions >= 3:
        engagement_score = 3
    elif weighted_interactions >= 1:
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